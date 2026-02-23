"""
音訊處理模組
負責從 YouTube 下載音訊，並進行音訊轉 MIDI 的處理。
"""

import os
import subprocess
import tempfile
from pathlib import Path

# yt-dlp 設定
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)


def download_youtube_audio(youtube_url: str) -> dict:
    """
    從 YouTube 連結下載音訊為 WAV 格式。

    Args:
        youtube_url: YouTube 影片的 URL

    Returns:
        dict: 包含 file_path, title, duration 等資訊
    """
    output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")

    # 使用 yt-dlp 下載並轉換為 WAV
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--output", output_template,
        "--print", "after_move:filepath",
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

        if len(lines) >= 3:
            file_path = lines[0].strip()
            title = lines[1].strip()
            duration = float(lines[2].strip()) if lines[2].strip() else 0
        else:
            # 嘗試從輸出中找到檔案
            file_path = lines[0].strip() if lines else ""
            title = "Unknown"
            duration = 0

        return {
            "success": True,
            "file_path": file_path,
            "title": title,
            "duration": duration,
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"下載失敗: {e.stderr}",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "下載超時（超過 5 分鐘）",
        }


def audio_to_midi_basic(wav_path: str, output_midi_path: str = None) -> dict:
    """
    將 WAV 音訊轉換為 MIDI。

    目前使用 yt-dlp 搭配外部工具的方式。
    未來可替換為 basic-pitch 或其他 AI 模型。

    Args:
        wav_path: WAV 檔案路徑
        output_midi_path: 輸出 MIDI 檔案路徑

    Returns:
        dict: 包含 midi_path 與處理狀態
    """
    if output_midi_path is None:
        output_midi_path = wav_path.replace(".wav", ".mid")

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
