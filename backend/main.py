"""
Music Tab Finder - FastAPI 後端
提供 YouTube 轉譜的 REST API。
"""

import os
import uuid
import json
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audio_processor import download_youtube_audio, audio_to_midi_basic, DOWNLOAD_DIR
from tab_engine import generate_chord_sheet, generate_fingerstyle_tab, generate_piano_sheet

app = FastAPI(
    title="Music Tab Finder API",
    description="從 YouTube 連結自動產生吉他簡譜、指彈譜與鋼琴譜",
    version="1.0.0",
)

# CORS 設定 - 允許前端跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 資料儲存 ──
HISTORY_FILE = Path(__file__).parent / "history.json"
FAVORITES_FILE = Path(__file__).parent / "favorites.json"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def load_json(path: Path) -> list:
    """載入 JSON 檔案。"""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path: Path, data: list):
    """儲存 JSON 檔案。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 請求模型 ──
class TranscribeRequest(BaseModel):
    """轉譜請求。"""
    youtube_url: str
    output_type: str = "chord_sheet"  # chord_sheet | fingerstyle_tab | piano_sheet
    key_offset: int = 0  # 調號偏移


class FavoriteRequest(BaseModel):
    """收藏請求。"""
    record_id: str


# ── API 路由 ──
@app.get("/api/status")
async def api_status():
    """API 狀態檢查。"""
    return {
        "status": "running",
        "name": "Music Tab Finder",
        "version": "1.0.0",
    }


@app.post("/api/transcribe")
async def transcribe(request: TranscribeRequest):
    """
    主要轉譜 API。

    流程：
    1. 從 YouTube 下載音訊
    2. 轉換為 MIDI
    3. 產生指定格式的樂譜
    """
    import traceback

    try:
        # Step 1: 下載 YouTube 音訊
        download_result = download_youtube_audio(request.youtube_url)
        if not download_result["success"]:
            raise HTTPException(status_code=400, detail=download_result.get("error", "下載失敗"))

        wav_path = download_result["file_path"]
        title = download_result.get("title", "Unknown")

        # Step 2: 音訊轉 MIDI
        midi_result = audio_to_midi_basic(wav_path)
        if not midi_result["success"]:
            raise HTTPException(status_code=500, detail=midi_result.get("error", "轉譜失敗"))

        midi_path = midi_result["midi_path"]

        # Step 3: 產生樂譜
        if request.output_type == "chord_sheet":
            sheet_result = generate_chord_sheet(midi_path, request.key_offset)
        elif request.output_type == "fingerstyle_tab":
            sheet_result = generate_fingerstyle_tab(midi_path)
        elif request.output_type == "piano_sheet":
            sheet_result = generate_piano_sheet(midi_path, request.key_offset)
        else:
            raise HTTPException(status_code=400, detail=f"不支援的輸出類型: {request.output_type}")

        if not sheet_result["success"]:
            raise HTTPException(status_code=500, detail=sheet_result.get("error", "樂譜產生失敗"))

        # 建立記錄
        record = {
            "id": str(uuid.uuid4()),
            "youtube_url": request.youtube_url,
            "title": title,
            "output_type": request.output_type,
            "content": sheet_result["content"],
            "tempo": sheet_result.get("tempo", 120),
            "key": sheet_result.get("key", "C"),
            "created_at": datetime.now().isoformat(),
            "midi_note": midi_result.get("note", ""),
        }

        # 儲存歷史記錄
        history = load_json(HISTORY_FILE)
        history.insert(0, record)
        history = history[:50]  # 只保留最近 50 筆
        save_json(HISTORY_FILE, history)

        return record
    except HTTPException:
        raise  # 讓 FastAPI 處理已知的 HTTP 異常
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"轉譜過程發生錯誤: {str(e)}")


@app.get("/api/history")
async def get_history():
    """取得轉譜歷史記錄。"""
    return load_json(HISTORY_FILE)


@app.post("/api/favorites")
async def add_favorite(request: FavoriteRequest):
    """將記錄加入收藏。"""
    history = load_json(HISTORY_FILE)
    record = next((r for r in history if r["id"] == request.record_id), None)

    if not record:
        raise HTTPException(status_code=404, detail="找不到該記錄")

    favorites = load_json(FAVORITES_FILE)

    # 避免重複收藏
    if any(f["id"] == request.record_id for f in favorites):
        return {"message": "已經收藏過了", "favorites": favorites}

    favorites.insert(0, record)
    save_json(FAVORITES_FILE, favorites)

    return {"message": "收藏成功", "favorites": favorites}


@app.get("/api/favorites")
async def get_favorites():
    """取得收藏清單。"""
    return load_json(FAVORITES_FILE)


@app.delete("/api/favorites/{record_id}")
async def remove_favorite(record_id: str):
    """取消收藏。"""
    favorites = load_json(FAVORITES_FILE)
    favorites = [f for f in favorites if f["id"] != record_id]
    save_json(FAVORITES_FILE, favorites)
    return {"message": "已取消收藏", "favorites": favorites}


@app.post("/api/export")
async def export_to_static():
    """
    匯出歷史記錄到前端靜態資料檔案。
    供 GitHub Pages 部署使用。
    """
    history = load_json(HISTORY_FILE)
    favorites = load_json(FAVORITES_FILE)

    # 合併歷史與收藏（去重）
    all_ids = set()
    all_sheets = []
    for record in history + favorites:
        if record["id"] not in all_ids:
            all_ids.add(record["id"])
            all_sheets.append(record)

    # 寫入前端靜態資料
    data_dir = FRONTEND_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / "sheets.json"
    save_json(output_path, all_sheets)

    return {
        "message": f"已匯出 {len(all_sheets)} 筆樂譜到 {output_path}",
        "count": len(all_sheets),
        "path": str(output_path),
    }


# ── 掛載前端靜態檔案 ──
if FRONTEND_DIR.exists():
    from fastapi.responses import FileResponse

    # 提供前端靜態資源
    app.mount("/public", StaticFiles(directory=str(FRONTEND_DIR / "public")), name="public")

    # 掛載 data 目錄（樂譜靜態資料）
    data_dir = FRONTEND_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

    @app.get("/styles.css")
    async def serve_css():
        return FileResponse(str(FRONTEND_DIR / "styles.css"), media_type="text/css")

    @app.get("/app.js")
    async def serve_js():
        return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript")

    @app.get("/sw.js")
    async def serve_sw():
        return FileResponse(str(FRONTEND_DIR / "sw.js"), media_type="application/javascript")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"), media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    print("\n🎵 Music Tab Finder 啟動中...\n")
    print("   前端介面: http://localhost:8000")
    print("   API 文件: http://localhost:8000/docs")
    print("   手機存取: http://<你的IP>:8000\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

