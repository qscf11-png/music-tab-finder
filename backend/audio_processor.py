"""
音訊處理模組
負責從 YouTube 下載音訊，並進行音訊轉 MIDI 的處理。
"""

import os
import subprocess
import tempfile
import sys
from pathlib import Path

# yt-dlp 設定
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 找到 yt-dlp 的執行路徑
def _get_ytdlp_cmd():
    """取得 yt-dlp 的執行指令（使用 Python 模組呼叫以避免 PATH 問題）。"""
    return [sys.executable, "-m", "yt_dlp"]


def download_youtube_audio(youtube_url: str) -> dict:
    """
    從 YouTube 連結下載音訊。

    嘗試轉換為 WAV（需要 ffmpeg），若無 ffmpeg 則直接下載原始音訊格式。

    Args:
        youtube_url: YouTube 影片的 URL

    Returns:
        dict: 包含 file_path, title, duration 等資訊
    """
    import shutil

    has_ffmpeg = shutil.which("ffmpeg") is not None
    output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")

    # 建立 yt-dlp 指令
    cmd = _get_ytdlp_cmd()

    if has_ffmpeg:
        cmd += ["--extract-audio", "--audio-format", "wav", "--audio-quality", "0"]
    else:
        # 無 ffmpeg：直接下載最佳音訊（不轉檔）
        cmd += ["-f", "bestaudio"]

    cmd += [
        "--output", output_template,
        "--print", "after_move:filepath" if has_ffmpeg else "after_filter:filepath",
        "--print", "%(title)s",
        "--print", "%(duration)s",
        "--no-playlist",
        youtube_url,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, check=True
        )
        lines = result.stdout.strip().split("\n")
        # 過濾掉空行
        lines = [l for l in lines if l.strip()]

        if len(lines) >= 3:
            file_path = lines[-3].strip()
            title = lines[-2].strip()
            duration_str = lines[-1].strip()
            try:
                duration = float(duration_str)
            except (ValueError, TypeError):
                duration = 0
        elif len(lines) >= 1:
            file_path = lines[0].strip()
            title = "Unknown"
            duration = 0
        else:
            return {"success": False, "error": "yt-dlp 未產生輸出"}

        # 確認檔案存在
        if not os.path.exists(file_path):
            # 嘗試從 downloads 目錄找到剛下載的檔案
            files = sorted(DOWNLOAD_DIR.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
            if files:
                file_path = str(files[0])
            else:
                return {"success": False, "error": f"找不到下載檔案: {file_path}"}

        return {
            "success": True,
            "file_path": file_path,
            "title": title,
            "duration": duration,
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or str(e)
        if "ffmpeg" in error_msg.lower():
            return {"success": False, "error": "需要安裝 ffmpeg。請執行: winget install ffmpeg"}
        return {"success": False, "error": f"下載失敗: {error_msg[:200]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "下載超時（超過 5 分鐘）"}


def audio_to_midi_basic(wav_path: str, output_midi_path: str = None) -> dict:
    """
    將音訊轉換為 MIDI。

    目前使用演示模式產生範例 MIDI。
    未來可替換為 basic-pitch 或其他 AI 模型。

    Args:
        wav_path: 音訊檔案路徑
        output_midi_path: 輸出 MIDI 檔案路徑

    Returns:
        dict: 包含 midi_path 與處理狀態
    """
    if output_midi_path is None:
        # 使用 Path 處理，支援任何音訊格式的副檔名
        p = Path(wav_path)
        output_midi_path = str(p.parent / (p.stem + ".mid"))

    # 注意：在 Windows 環境下，basic-pitch 的 TensorFlow 依賴有相容性問題。
    # 這裡提供一個模擬的 MIDI 產生功能作為演示。
    # 實際部署時，建議在 Linux/Docker 環境中使用 basic-pitch。
    try:
        import pretty_midi

        # 建立一個示範用的 MIDI（實際應由 AI 模型產生）
        midi = pretty_midi.PrettyMIDI()
        guitar = pretty_midi.Instrument(program=25, name="Guitar")  # Acoustic Guitar (steel)
        piano_inst = pretty_midi.Instrument(program=0, name="Piano")

        # 示範：產生一段簡單的 C 大調音階作為預留位置
        # 實際使用時，這段邏輯會被 basic-pitch 的輸出取代
        c_major = [60, 62, 64, 65, 67, 69, 71, 72]  # C D E F G A B C
        for i, pitch in enumerate(c_major):
            note = pretty_midi.Note(
                velocity=100,
                pitch=pitch,
                start=i * 0.5,
                end=(i + 1) * 0.5,
            )
            piano_inst.notes.append(note)

        midi.instruments.append(piano_inst)
        midi.instruments.append(guitar)
        midi.write(output_midi_path)

        return {
            "success": True,
            "midi_path": output_midi_path,
            "message": "MIDI 檔案已產生（演示模式）",
            "note": "完整 AI 轉譜功能需在 Linux/Docker 環境部署 basic-pitch",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"MIDI 產生失敗: {str(e)}",
        }


def cleanup_downloads(max_age_hours: int = 24):
    """清理超過指定時間的下載檔案。"""
    import time

    now = time.time()
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age_hours * 3600:
            f.unlink()
