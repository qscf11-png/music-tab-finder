"""
樂譜產生引擎
負責將 MIDI 資訊轉換為吉他簡譜（彈唱）與指彈六線譜。
"""

import pretty_midi
from typing import Optional


# ── 音符名稱對照表 ──
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ── 簡譜數字對照 (以 C 大調為基準) ──
# C=1, D=2, E=3, F=4, G=5, A=6, B=7
NUMBERED_NOTATION_MAP = {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"}

# ── 吉他標準調弦 (E2, A2, D3, G3, B3, E4) ──
GUITAR_TUNING = [40, 45, 50, 55, 59, 64]
GUITAR_STRING_NAMES = ["e", "B", "G", "D", "A", "E"]  # 第1弦到第6弦


# ── 常見和弦模板 ──
CHORD_TEMPLATES = {
    "C":  [0, 4, 7],
    "Cm": [0, 3, 7],
    "D":  [2, 6, 9],
    "Dm": [2, 5, 9],
    "E":  [4, 8, 11],
    "Em": [4, 7, 11],
    "F":  [5, 9, 0],
    "Fm": [5, 8, 0],
    "G":  [7, 11, 2],
    "Gm": [7, 10, 2],
    "A":  [9, 1, 4],
    "Am": [9, 0, 4],
    "B":  [11, 3, 6],
    "Bm": [11, 2, 6],
}


def midi_note_to_name(midi_note: int) -> str:
    """將 MIDI 音符編號轉換為音符名稱（如 C4, D#5）。"""
    octave = (midi_note // 12) - 1
    note_name = NOTE_NAMES[midi_note % 12]
    return f"{note_name}{octave}"


def midi_note_to_numbered(midi_note: int, key_offset: int = 0) -> str:
    """
    將 MIDI 音符轉換為簡譜數字表示。

    Args:
        midi_note: MIDI 音符編號 (0-127)
        key_offset: 調號偏移（0=C 大調）

    Returns:
        str: 簡譜表示，如 "1", "2#", "5.", "1̇" 等
    """
    note_in_scale = (midi_note - key_offset) % 12
    octave = (midi_note - 60) // 12  # 以 C4 為中心

    # 查找最接近的簡譜數字
    if note_in_scale in NUMBERED_NOTATION_MAP:
        num = NUMBERED_NOTATION_MAP[note_in_scale]
    else:
        # 升降音用 # 或 b 標記
        lower = note_in_scale - 1
        if lower in NUMBERED_NOTATION_MAP:
            num = NUMBERED_NOTATION_MAP[lower] + "#"
        else:
            num = str(note_in_scale)

    # 八度標記
    if octave > 0:
        num = num + "·" * octave  # 高八度加點
    elif octave < 0:
        num = num + "," * abs(octave)  # 低八度加逗號

    return num


def detect_chord(notes: list[int]) -> str:
    """
    從一組同時發聲的音符中辨識和弦。

    Args:
        notes: MIDI 音符編號列表

    Returns:
        str: 和弦名稱（如 "Am", "G"）
    """
    if not notes:
        return ""

    pitch_classes = sorted(set(n % 12 for n in notes))

    best_match = ""
    best_score = 0

    for chord_name, template in CHORD_TEMPLATES.items():
        score = sum(1 for pc in pitch_classes if pc in template)
        if score > best_score:
            best_score = score
            best_match = chord_name

    return best_match if best_score >= 2 else ""


def midi_note_to_guitar_fret(midi_note: int) -> Optional[tuple[int, int]]:
    """
    將 MIDI 音符映射到吉他的弦與品。

    Args:
        midi_note: MIDI 音符編號

    Returns:
        tuple: (弦號 1-6, 品號 0-24) 或 None
    """
    best_string = None
    best_fret = None
    min_fret = float("inf")

    for string_idx, open_note in enumerate(GUITAR_TUNING):
        fret = midi_note - open_note
        if 0 <= fret <= 24:
            # 優先選擇低品位（更容易彈奏）
            if fret < min_fret:
                min_fret = fret
                best_string = string_idx + 1  # 1-based
                best_fret = fret

    if best_string is not None:
        return (best_string, best_fret)
    return None


def generate_chord_sheet(midi_path: str, key_offset: int = 0) -> dict:
    """
    從 MIDI 檔案產生彈唱簡譜。

    包含：
    - 旋律線（數字簡譜 1234567）
    - 和弦標記（Am, G, C 等）

    Args:
        midi_path: MIDI 檔案路徑
        key_offset: 調號偏移

    Returns:
        dict: 包含簡譜內容
    """
    try:
        midi = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        return {"success": False, "error": f"無法讀取 MIDI: {str(e)}"}

    result_lines = []
    chord_line = []
    melody_line = []

    # 取得所有音符並按時間排序
    all_notes = []
    for instrument in midi.instruments:
        if not instrument.is_drum:
            for note in instrument.notes:
                all_notes.append(note)

    all_notes.sort(key=lambda n: n.start)

    if not all_notes:
        return {"success": False, "error": "MIDI 檔案中沒有音符"}

    # 以拍為單位分組（假設 120 BPM，每拍 0.5 秒）
    tempo = midi.estimate_tempo() or 120
    beat_duration = 60.0 / tempo
    total_duration = midi.get_end_time()

    current_beat = 0
    beat_time = 0.0

    measures = []
    current_measure_melody = []
    current_measure_chords = []
    beats_per_measure = 4

    while beat_time < total_duration:
        beat_end = beat_time + beat_duration

        # 找到這一拍內的音符
        beat_notes = [n for n in all_notes if n.start >= beat_time and n.start < beat_end]

        if beat_notes:
            # 旋律：取最高音
            melody_note = max(beat_notes, key=lambda n: n.pitch)
            numbered = midi_note_to_numbered(melody_note.pitch, key_offset)
            current_measure_melody.append(numbered)

            # 和弦：從所有音符中辨識
            chord = detect_chord([n.pitch for n in beat_notes])
            current_measure_chords.append(chord)
        else:
            current_measure_melody.append("-")
            current_measure_chords.append("")

        current_beat += 1

        if current_beat >= beats_per_measure:
            measures.append({
                "melody": current_measure_melody,
                "chords": current_measure_chords,
            })
            current_measure_melody = []
            current_measure_chords = []
            current_beat = 0

        beat_time = beat_end

    # 處理最後不完整的小節
    if current_measure_melody:
        measures.append({
            "melody": current_measure_melody,
            "chords": current_measure_chords,
        })

    # 格式化輸出
    output_lines = []
    output_lines.append(f"速度: ♩ = {int(tempo)}")
    output_lines.append(f"調號: {NOTE_NAMES[key_offset % 12]} 大調")
    output_lines.append("")

    for i, measure in enumerate(measures):
        # 和弦行
        chord_display = []
        last_chord = ""
        for ch in measure["chords"]:
            if ch and ch != last_chord:
                chord_display.append(f"[{ch}]")
                last_chord = ch
            else:
                chord_display.append("    ")

        # 旋律行
        melody_display = " ".join(f"{m:>3}" for m in measure["melody"])

        chord_str = " ".join(f"{c:>5}" for c in chord_display)
        output_lines.append(chord_str)
        output_lines.append(melody_display)

        if (i + 1) % 4 == 0:
            output_lines.append("")  # 每 4 小節空一行

    return {
        "success": True,
        "content": "\n".join(output_lines),
        "measures": measures,
        "tempo": int(tempo),
        "key": NOTE_NAMES[key_offset % 12],
    }


def generate_fingerstyle_tab(midi_path: str) -> dict:
    """
    從 MIDI 檔案產生指彈六線譜。

    Args:
        midi_path: MIDI 檔案路徑

    Returns:
        dict: 包含六線譜內容
    """
    try:
        midi = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        return {"success": False, "error": f"無法讀取 MIDI: {str(e)}"}

    # 收集所有非鼓的音符
    all_notes = []
    for instrument in midi.instruments:
        if not instrument.is_drum:
            for note in instrument.notes:
                fret_info = midi_note_to_guitar_fret(note.pitch)
                if fret_info:
                    all_notes.append({
                        "pitch": note.pitch,
                        "start": note.start,
                        "end": note.end,
                        "string": fret_info[0],
                        "fret": fret_info[1],
                    })

    all_notes.sort(key=lambda n: n["start"])

    if not all_notes:
        return {"success": False, "error": "沒有可轉換為吉他譜的音符"}

    # 建立六線譜
    tempo = midi.estimate_tempo() or 120
    beat_duration = 60.0 / tempo
    total_duration = midi.get_end_time()
    total_columns = int(total_duration / beat_duration) + 1

    # 初始化六條弦的陣列
    tab_lines = {i: [] for i in range(1, 7)}  # 弦 1-6
    for string_num in range(1, 7):
        tab_lines[string_num] = ["-"] * total_columns

    # 填入音符
    for note in all_notes:
        col = int(note["start"] / beat_duration)
        if col < total_columns:
            fret_str = str(note["fret"])
            tab_lines[note["string"]][col] = fret_str

    # 格式化輸出（每行顯示 32 拍）
    output_lines = []
    output_lines.append(f"速度: ♩ = {int(tempo)}")
    output_lines.append(f"Tuning: Standard (EADGBE)")
    output_lines.append("")

    chunk_size = 32
    for chunk_start in range(0, total_columns, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_columns)

        for string_num in range(1, 7):
            string_name = GUITAR_STRING_NAMES[string_num - 1]
            frets = tab_lines[string_num][chunk_start:chunk_end]
            line = f"{string_name}|" + "-".join(f"{f:>2}" for f in frets) + "|"
            output_lines.append(line)

        output_lines.append("")  # 段落間空行

    return {
        "success": True,
        "content": "\n".join(output_lines),
        "tempo": int(tempo),
        "total_notes": len(all_notes),
    }


def generate_piano_sheet(midi_path: str, key_offset: int = 0) -> dict:
    """
    從 MIDI 檔案產生鋼琴簡譜。

    Args:
        midi_path: MIDI 檔案路徑
        key_offset: 調號偏移

    Returns:
        dict: 包含鋼琴簡譜內容
    """
    try:
        midi = pretty_midi.PrettyMIDI(midi_path)
    except Exception as e:
        return {"success": False, "error": f"無法讀取 MIDI: {str(e)}"}

    all_notes = []
    for instrument in midi.instruments:
        if not instrument.is_drum:
            for note in instrument.notes:
                all_notes.append(note)

    all_notes.sort(key=lambda n: n.start)

    if not all_notes:
        return {"success": False, "error": "MIDI 檔案中沒有音符"}

    tempo = midi.estimate_tempo() or 120
    beat_duration = 60.0 / tempo
    total_duration = midi.get_end_time()

    # 分為右手（高音）和左手（低音）
    right_hand = []
    left_hand = []

    beat_time = 0.0
    while beat_time < total_duration:
        beat_end = beat_time + beat_duration
        beat_notes = [n for n in all_notes if n.start >= beat_time and n.start < beat_end]

        rh_notes = [n for n in beat_notes if n.pitch >= 60]  # C4 以上
        lh_notes = [n for n in beat_notes if n.pitch < 60]   # C4 以下

        if rh_notes:
            top = max(rh_notes, key=lambda n: n.pitch)
            right_hand.append(midi_note_to_numbered(top.pitch, key_offset))
        else:
            right_hand.append("-")

        if lh_notes:
            bottom = min(lh_notes, key=lambda n: n.pitch)
            left_hand.append(midi_note_to_numbered(bottom.pitch, key_offset))
        else:
            left_hand.append("-")

        beat_time = beat_end

    # 格式化
    output_lines = [
        f"速度: ♩ = {int(tempo)}",
        f"調號: {NOTE_NAMES[key_offset % 12]} 大調",
        "",
        "右手（旋律）：",
    ]

    # 每 16 拍一行
    for i in range(0, len(right_hand), 16):
        chunk = right_hand[i:i + 16]
        output_lines.append(" ".join(f"{n:>3}" for n in chunk))

    output_lines.append("")
    output_lines.append("左手（伴奏）：")

    for i in range(0, len(left_hand), 16):
        chunk = left_hand[i:i + 16]
        output_lines.append(" ".join(f"{n:>3}" for n in chunk))

    return {
        "success": True,
        "content": "\n".join(output_lines),
        "tempo": int(tempo),
        "key": NOTE_NAMES[key_offset % 12],
    }
