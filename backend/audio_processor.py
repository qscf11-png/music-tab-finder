"""
音訊處理模組
負責從 YouTube 下載音訊，並使用 librosa 進行音高偵測轉換為 MIDI。
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

# yt-dlp 設定
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)


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
        lines = [l for l in lines if l.strip()]

        if len(lines) >= 3:
            file_path = lines[-3].strip()
            title = lines[-2].strip()
            try:
                duration = float(lines[-1].strip())
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


def audio_to_midi(audio_path: str, output_midi_path: str = None) -> dict:
    """
    使用 librosa 進行音高偵測，將音訊轉換為 MIDI。

    使用 pyin 演算法偵測旋律音高，配合 onset detection 偵測音符起始位置，
    再使用 beat tracking 分析節拍。

    Args:
        audio_path: 音訊檔案路徑（支援 wav, webm, m4a 等）
        output_midi_path: 輸出 MIDI 檔案路徑

    Returns:
        dict: 包含 midi_path、tempo、key 等資訊
    """
    if output_midi_path is None:
        p = Path(audio_path)
        output_midi_path = str(p.parent / (p.stem + ".mid"))

    try:
        import librosa
        import pretty_midi

        print(f"📊 載入音訊: {audio_path}")
        # 載入音訊（librosa 支援多種格式，會自動用 soundfile 或 audioread）
        y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=180)
        print(f"   取樣率: {sr}, 長度: {len(y)/sr:.1f}秒")

        # ── 節拍偵測 ──
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        # tempo 可能是陣列
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            tempo = float(tempo)
        tempo = max(60, min(200, tempo))  # 限制合理範圍
        print(f"   偵測 BPM: {tempo:.0f}")

        # ── 音高偵測 (pyin) ──
        # pyin 比 piptrack 更適合單旋律偵測
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y, fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )

        # 將頻率轉為 MIDI 音高
        times = librosa.times_like(f0, sr=sr)

        # ── Onset 偵測 ──
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        # ── 建立 MIDI ──
        midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
        melody = pretty_midi.Instrument(program=0, name="Melody")
        bass_line = pretty_midi.Instrument(program=25, name="Guitar")

        # 從 pyin 結果中提取音符
        notes = _extract_notes_from_pyin(f0, voiced_flag, times, onset_times)
        print(f"   偵測到 {len(notes)} 個音符")

        if len(notes) < 5:
            return {
                "success": False,
                "error": "偵測到的音符太少，可能是音訊品質不佳或格式不支援"
            }

        for note_info in notes:
            note = pretty_midi.Note(
                velocity=int(note_info['velocity']),
                pitch=int(note_info['pitch']),
                start=float(note_info['start']),
                end=float(note_info['end']),
            )
            melody.notes.append(note)

        midi.instruments.append(melody)

        # 簡單的和弦推論（根據音符分布推估和弦進行）
        chords = _estimate_chord_progression(notes, tempo)
        for chord_note in chords:
            n = pretty_midi.Note(
                velocity=70,
                pitch=int(chord_note['pitch']),
                start=float(chord_note['start']),
                end=float(chord_note['end']),
            )
            bass_line.notes.append(n)

        midi.instruments.append(bass_line)

        # 調性分析
        key = _detect_key(notes)

        midi.write(output_midi_path)
        print(f"   ✅ MIDI 已產生: {output_midi_path}")

        return {
            "success": True,
            "midi_path": output_midi_path,
            "tempo": round(tempo),
            "key": key,
            "note_count": len(notes),
            "note": f"使用 librosa pyin 偵測到 {len(notes)} 個音符",
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"音訊分析失敗: {str(e)}",
        }


def _extract_notes_from_pyin(f0, voiced_flag, times, onset_times):
    """
    從 pyin 的結果提取音符列表。

    將連續的相同音高合併為一個音符，配合 onset 偵測確定音符邊界。
    """
    notes = []
    current_pitch = None
    current_start = None
    min_duration = 0.08  # 最短音符長度（秒）

    for i in range(len(f0)):
        if voiced_flag[i] and not np.isnan(f0[i]):
            midi_pitch = int(round(librosa_hz_to_midi(f0[i])))
            midi_pitch = max(21, min(108, midi_pitch))  # 鋼琴範圍

            # 檢查是否有新的 onset
            is_new_onset = False
            for onset_t in onset_times:
                if abs(times[i] - onset_t) < 0.05:
                    is_new_onset = True
                    break

            if current_pitch is None:
                # 新音符開始
                current_pitch = midi_pitch
                current_start = times[i]
            elif midi_pitch != current_pitch or is_new_onset:
                # 音高改變或新 onset → 結束前一個音符
                duration = times[i] - current_start
                if duration >= min_duration:
                    velocity = min(120, max(60, 80 + int((duration - 0.1) * 40)))
                    notes.append({
                        'pitch': current_pitch,
                        'start': current_start,
                        'end': times[i],
                        'velocity': velocity,
                    })
                current_pitch = midi_pitch
                current_start = times[i]
        else:
            # 無聲區段 → 結束當前音符
            if current_pitch is not None:
                duration = times[i] - current_start
                if duration >= min_duration:
                    velocity = min(120, max(60, 80))
                    notes.append({
                        'pitch': current_pitch,
                        'start': current_start,
                        'end': times[i],
                        'velocity': velocity,
                    })
                current_pitch = None
                current_start = None

    # 處理最後一個音符
    if current_pitch is not None and current_start is not None:
        end_time = times[-1] if len(times) > 0 else current_start + 0.25
        duration = end_time - current_start
        if duration >= min_duration:
            notes.append({
                'pitch': current_pitch,
                'start': current_start,
                'end': end_time,
                'velocity': 80,
            })

    return notes


def _estimate_chord_progression(notes, tempo):
    """
    根據旋律音符簡單推估和弦進行。
    每小節取該小節中出現頻率最高的音做為根音。
    """
    if not notes:
        return []

    beat_duration = 60.0 / tempo
    bar_duration = beat_duration * 4  # 4/4 拍
    total_duration = max(n['end'] for n in notes)
    chord_notes = []

    # 常見和弦根音對照
    for bar_start in np.arange(0, total_duration, bar_duration):
        bar_end = bar_start + bar_duration
        # 收集此小節的音高
        pitches_in_bar = []
        for n in notes:
            if n['start'] >= bar_start and n['start'] < bar_end:
                pitches_in_bar.append(n['pitch'] % 12)

        if not pitches_in_bar:
            continue

        # 找到出現最多次的音作為根音
        pitch_counts = {}
        for p in pitches_in_bar:
            pitch_counts[p] = pitch_counts.get(p, 0) + 1
        root = max(pitch_counts, key=pitch_counts.get)

        # 加入根音（低一個八度）
        bass_pitch = 36 + root  # C2 起
        chord_notes.append({
            'pitch': bass_pitch,
            'start': bar_start,
            'end': bar_end,
        })

    return chord_notes


def _detect_key(notes):
    """
    根據音符分布偵測調性。
    使用 Krumhansl-Kessler 音調剖面（簡化版）。
    """
    if not notes:
        return "C"

    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    # 計算各音名出現次數
    pitch_histogram = [0] * 12
    for n in notes:
        pitch_class = n['pitch'] % 12
        duration = n['end'] - n['start']
        pitch_histogram[pitch_class] += duration

    # 大調的 Krumhansl-Kessler profile
    major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]

    # 嘗試每個調
    best_key = "C"
    best_corr = -1

    for shift in range(12):
        shifted = pitch_histogram[shift:] + pitch_histogram[:shift]
        # 計算相關係數
        mean_s = sum(shifted) / 12
        mean_p = sum(major_profile) / 12
        numerator = sum((s - mean_s) * (p - mean_p) for s, p in zip(shifted, major_profile))
        denom_s = sum((s - mean_s) ** 2 for s in shifted) ** 0.5
        denom_p = sum((p - mean_p) ** 2 for p in major_profile) ** 0.5

        if denom_s > 0 and denom_p > 0:
            corr = numerator / (denom_s * denom_p)
            if corr > best_corr:
                best_corr = corr
                best_key = NOTE_NAMES[shift]

    return best_key


def librosa_hz_to_midi(freq):
    """將頻率 (Hz) 轉換為 MIDI 音高。"""
    if freq <= 0:
        return 0
    return 69 + 12 * np.log2(freq / 440.0)


# 保持向後相容
audio_to_midi_basic = audio_to_midi


def cleanup_downloads(max_age_hours: int = 24):
    """清理超過指定時間的下載檔案。"""
    import time

    now = time.time()
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age_hours * 3600:
            f.unlink()
