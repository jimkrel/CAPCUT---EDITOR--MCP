"""
autoedit_engine.py - Engine Biên Tập Tự Động CapCut Desktop Chuẩn Beat-Sync & Quote Detection
Thiết kế theo đúng triết lý của Eleven Percent AUTOEDIT:
1. Nhận 3 Input: Nhạc (Music) + Phỏng Vấn (Interview) + Kho B-Roll
2. Tự động bắt beat & BPM bài nhạc (FFmpeg + NumPy Energy Flux) -> Tạo Beat Markers chấm vàng
3. Tự động bóc tách câu thoại (faster-whisper) -> Tạo phụ đề Safe Zone & Auto Ducking BGM
4. Tự động cắt gọt B-Roll chuẩn từng nhịp Beat (Cut-on-Beat)
5. Xuất thẳng ra draft_content.json và mở CapCut Desktop vào Timeline!
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import numpy as np

# Thêm đường dẫn hiện tại vào sys.path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import register_draft
import capcut_automator

logger = logging.getLogger("autoedit_engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS_DIR = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft" if LOCALAPPDATA else Path.home() / "CapCutDrafts"

WIN_FONTS = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts" if LOCALAPPDATA else Path()
FONT_REGULAR = str(WIN_FONTS / "Montserrat-Regular.otf").replace("\\", "/") if (WIN_FONTS / "Montserrat-Regular.otf").exists() else "Montserrat-Regular.otf"
FONT_BOLD = str(WIN_FONTS / "Montserrat-Bold.otf").replace("\\", "/") if (WIN_FONTS / "Montserrat-Bold.otf").exists() else "Montserrat-Bold.otf"

def uuidv4():
    return str(uuid.uuid4()).upper()

# =====================================================================
# 1. AUDIO BEAT & ONSET DETECTION ENGINE (Native FFmpeg + NumPy)
# =====================================================================
def detect_audio_beats(audio_path: str, hop_size: int = 512, sr: int = 22050, min_bpm: int = 70, max_bpm: int = 185) -> Dict[str, Any]:
    """
    Dò nhịp beat và BPM của bài nhạc bằng thuật toán Onset Energy Flux thuần:
    - Đọc raw PCM f32le qua FFmpeg (không cần lib ngoài)
    - Tính Energy Flux & Smooth threshold
    - Trả về danh sách mốc thời gian (giây và micro-giây)
    """
    p = Path(audio_path)
    if not p.exists():
        return {"ok": False, "error": f"Không tìm thấy file nhạc: {audio_path}"}

    cmd = [
        "ffmpeg", "-v", "error", "-i", str(p),
        "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw_data, _ = proc.communicate()

    if not raw_data:
        return {"ok": False, "error": "FFmpeg không thể trích xuất audio"}

    samples = np.frombuffer(raw_data, dtype=np.float32)
    duration_sec = len(samples) / sr

    frame_len = 1024
    hop = hop_size
    n_frames = (len(samples) - frame_len) // hop
    if n_frames <= 1:
        return {"ok": True, "beats_sec": [0.0], "beats_us": [0], "duration_sec": duration_sec, "bpm": 120}

    # Tính năng lượng frame
    energy = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        start = i * hop
        seg = samples[start:start+frame_len]
        energy[i] = np.sum(seg ** 2)

    # Onset Envelope (Energy Flux)
    diff = np.diff(energy, prepend=energy[0])
    flux = np.maximum(0, diff)
    max_flux = np.max(flux)
    if max_flux > 0:
        flux = flux / max_flux

    min_dist_frames = int((60.0 / max_bpm) * (sr / hop))
    window_sz = int(0.5 * (sr / hop))
    if window_sz % 2 == 0:
        window_sz += 1

    kernel = np.ones(window_sz) / window_sz
    smooth_flux = np.convolve(flux, kernel, mode="same")
    threshold = smooth_flux + 0.15 * np.std(flux)

    beats_sec = []
    last_beat_frame = -min_dist_frames
    for i in range(1, n_frames - 1):
        if flux[i] > threshold[i] and flux[i] > flux[i-1] and flux[i] >= flux[i+1]:
            if (i - last_beat_frame) >= min_dist_frames:
                t_sec = round((i * hop) / sr, 3)
                beats_sec.append(t_sec)
                last_beat_frame = i

    beats_us = [int(round(t * 1e6)) for t in beats_sec]

    bpm = 120.0
    if len(beats_sec) > 1:
        intervals = np.diff(beats_sec)
        med = float(np.median(intervals))
        if med > 0:
            bpm = round(60.0 / med, 1)

    return {
        "ok": True,
        "duration_sec": round(duration_sec, 2),
        "duration_us": int(round(duration_sec * 1e6)),
        "bpm": bpm,
        "beat_count": len(beats_sec),
        "beats_sec": beats_sec,
        "beats_us": beats_us
    }

# =====================================================================
# 2. INTERVIEW QUOTE DETECTION ENGINE (faster-whisper)
# =====================================================================
def extract_interview_quotes(interview_path: str) -> List[Dict[str, Any]]:
    """
    Bóc tách lời thoại và mốc thời gian từ clip phỏng vấn / VJ bằng faster-whisper.
    """
    if not interview_path or not Path(interview_path).exists():
        return []

    quotes = []
    try:
        from faster_whisper import WhisperModel
        logger.info(f"Đang bóc tách câu thoại từ: {Path(interview_path).name}...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(interview_path), language="vi")
        for seg in segments:
            text = seg.text.strip()
            if len(text) > 2:
                quotes.append({
                    "startSec": round(seg.start, 2),
                    "endSec": round(seg.end, 2),
                    "durationSec": round(seg.end - seg.start, 2),
                    "startUs": int(round(seg.start * 1e6)),
                    "durationUs": int(round((seg.end - seg.start) * 1e6)),
                    "text": text
                })
        logger.info(f"Đã tìm thấy {len(quotes)} câu thoại / quotes.")
    except Exception as e:
        logger.warning(f"Không thể bóc tách quotes qua faster-whisper: {e}")
    return quotes

# =====================================================================
# 3. FOOTAGE SCANNER (B-Roll Pool)
# =====================================================================
def get_broll_files(broll_folder: str) -> List[Path]:
    """Lấy danh sách các tệp video B-Roll hợp lệ trong thư mục."""
    if not broll_folder or not Path(broll_folder).exists():
        return []
    exts = {".mp4", ".mov", ".mkv", ".avi"}
    folder = Path(broll_folder)
    return [f for f in sorted(folder.iterdir()) if f.suffix.lower() in exts and f.is_file()]

def sanitize_media_path(file_path: Union[str, Path], staging_dir: Optional[Path] = None) -> str:
    """
    Chuẩn hóa đường dẫn tệp đa phương tiện cho CapCut Desktop:
    - Loại bỏ ký tự Unicode Private Use Area (như \uf022 sinh ra từ tên thư mục chứa dấu ':' trên exFAT)
    - Tự động sao chép sang thư mục staging sạch nếu đường dẫn chứa ký tự bất thường gây crash C++ engine.
    """
    if not file_path:
        return ""
    p = Path(file_path)
    raw_str = str(p.resolve())
    has_pua = any(0xE000 <= ord(c) <= 0xF8FF for c in raw_str)
    if has_pua and staging_dir:
        staging_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in p.name if c.isalnum() or c in (".", "-", "_"))
        target = staging_dir / safe_name
        if not target.exists() or target.stat().st_size != p.stat().st_size:
            import shutil
            shutil.copy2(p, target)
        return str(target).replace("\\", "/")
    return raw_str.replace("\\", "/")

# =====================================================================
# 4. CAPCUT DRAFT TIMELINE COMPILER (Pure Python)
# =====================================================================
def build_autoedit_draft(
    project_name: str,
    music_path: str,
    interview_path: str = "",
    broll_folder: str = "",
    pacing_mode: str = "medium",  # "fast" (mỗi 1 beat), "medium" (mỗi 2 beats), "cinematic" (mỗi 4 beats)
    hook_text: str = ""
) -> Dict[str, Any]:
    """
    Biên dịch draft CapCut hoàn chỉnh:
    - BGM Track: gắn user_beats chấm vàng
    - Main Video Track: Các phân đoạn B-roll cắt chuẩn theo beat + Interview clips
    - Voice Track: Audio phỏng vấn (nếu có)
    - Subtitle Track: Phụ đề thương mại Safe Zone (y = -0.404)
    - BGM Ducking: Tự động dìm nhỏ nhạc khi có phỏng vấn
    """
    if not project_name:
        project_name = f"AUTOEDIT_{int(time.time())}"
    safe_name = "".join(c for c in project_name if c.isalnum() or c in ("-", "_", " ")).strip()

    draft_dir = CAPCUT_DRAFTS_DIR / safe_name
    draft_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dò beat của bài nhạc
    beat_info = detect_audio_beats(music_path)
    if not beat_info.get("ok"):
        return {"ok": False, "error": beat_info.get("error")}

    beats_sec = beat_info["beats_sec"]
    beats_us = beat_info["beats_us"]
    music_duration_us = beat_info["duration_us"]

    # Bước nhảy beat (Pacing step)
    step = 2
    if pacing_mode == "fast":
        step = 1
    elif pacing_mode == "cinematic":
        step = 4

    # Chọn các mốc beat dùng để cắt
    cut_points_us = []
    if beats_us:
        cut_points_us = beats_us[::step]
        if cut_points_us[-1] < music_duration_us:
            cut_points_us.append(music_duration_us)
    else:
        # Fallback nếu nhạc không có beat rõ ràng: cắt mỗi 2.0s
        step_us = 2000000
        cut_points_us = list(range(0, music_duration_us, step_us)) + [music_duration_us]

    # 2. Lấy quotes từ phỏng vấn nếu có
    quotes = []
    if interview_path and Path(interview_path).exists():
        quotes = extract_interview_quotes(interview_path)

    # 3. Lấy kho B-Roll
    broll_files = get_broll_files(broll_folder)

    # Cấu trúc Materials & Tracks chuẩn CapCut Desktop
    materials = {
        "videos": [],
        "audios": [],
        "texts": [],
        "speeds": [],
        "canvases": [],
        "beats": [],
        "material_animations": [],
        "video_effects": [],
        "transitions": []
    }

    def add_speed(speed_val=1.0):
        s_id = uuidv4()
        materials["speeds"].append({"id": s_id, "mode": 0, "speed": float(speed_val), "type": "speed"})
        return s_id

    def add_canvas():
        c_id = uuidv4()
        materials["canvases"].append({"id": c_id, "type": "canvas_color", "color": "#00000000"})
        return c_id

    staging_audio = draft_dir / "materials" / "audio"
    staging_video = draft_dir / "materials" / "video"

    # 4. Đăng ký BGM Material & Beat Material
    bgm_mat_id = uuidv4()
    bgm_path_norm = sanitize_media_path(music_path, staging_audio)
    materials["audios"].append({
        "id": bgm_mat_id,
        "type": "audio",
        "path": bgm_path_norm,
        "media_path": bgm_path_norm,
        "duration": music_duration_us,
        "material_name": Path(music_path).name
    })

    # Chấm vàng Beat Markers trong CapCut
    beat_mat_id = uuidv4()
    materials["beats"].append({
        "id": beat_mat_id,
        "type": "beats",
        "enable_ai_beats": False,
        "gear": 404,
        "gear_count": 0,
        "mode": 404,
        "user_beats": beats_us,
        "user_delete_ai_beats": None,
        "ai_beats": {
            "melody_url": "",
            "melody_path": "",
            "beats_url": "",
            "beats_path": "",
            "melody_percents": [0.0],
            "beat_speed_infos": []
        }
    })

    # Đăng ký Interview Media nếu có
    interview_video_mat_id = None
    interview_audio_mat_id = None
    if interview_path and Path(interview_path).exists():
        norm_iv = sanitize_media_path(interview_path, staging_video)
        interview_video_mat_id = uuidv4()
        interview_audio_mat_id = uuidv4()
        materials["videos"].append({
            "id": interview_video_mat_id,
            "type": "video",
            "path": norm_iv,
            "media_path": norm_iv,
            "width": 1080,
            "height": 1920,
            "duration": 3600000000,
            "has_audio": True,
            "material_name": Path(interview_path).name
        })
        materials["audios"].append({
            "id": interview_audio_mat_id,
            "type": "audio",
            "path": norm_iv,
            "media_path": norm_iv,
            "duration": 3600000000,
            "material_name": Path(interview_path).name
        })

    # Đăng ký B-Roll materials
    broll_mat_ids = []
    for bf in broll_files:
        norm_bf = sanitize_media_path(bf, staging_video)
        m_id = uuidv4()
        materials["videos"].append({
            "id": m_id,
            "type": "video",
            "path": norm_bf,
            "media_path": norm_bf,
            "width": 1080,
            "height": 1920,
            "duration": 3600000000,
            "has_audio": False,
            "material_name": bf.name
        })
        broll_mat_ids.append(m_id)

    # 5. Xây dựng các Tracks:
    # Track 0: Main Video (B-Roll cắt theo Beat & Interview clips)
    # Track 1: Subtitles (Phụ đề cho phỏng vấn / hook)
    # Track 2: Voice Audio (Giọng phỏng vấn)
    # Track 3: BGM Audio (Nhạc nền có user_beats)
    track_video = {"id": uuidv4(), "type": "video", "flag": 0, "segments": []}
    track_sub = {"id": uuidv4(), "type": "text", "flag": 1, "segments": []}
    track_voice = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}
    track_bgm = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}

    # Chia dòng thời gian theo beat và interview
    current_timeline_us = 0
    broll_idx = 0
    num_broll = len(broll_mat_ids)

    # Tạo timeline dựa trên các cut points
    for i in range(len(cut_points_us) - 1):
        seg_start_us = cut_points_us[i]
        seg_end_us = cut_points_us[i+1]
        seg_dur_us = seg_end_us - seg_start_us
        if seg_dur_us <= 0:
            continue

        # Kiểm tra xem khoảng thời gian này có trùng với quote phỏng vấn nào không
        matched_quote = None
        for q in quotes:
            if q["startUs"] <= seg_start_us < q["startUs"] + q["durationUs"]:
                matched_quote = q
                break

        if matched_quote and interview_video_mat_id:
            # Chèn Interview clip
            spd_id = add_speed()
            cvs_id = add_canvas()
            track_video["segments"].append({
                "id": uuidv4(),
                "material_id": interview_video_mat_id,
                "extra_material_refs": [spd_id, cvs_id],
                "source_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                "target_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                "clip": {"scale": {"x": 1, "y": 1}, "transform": {"x": 0, "y": 0}},
                "volume": 0.0,
                "visible": True
            })
            # Voice Audio
            v_spd_id = add_speed()
            track_voice["segments"].append({
                "id": uuidv4(),
                "material_id": interview_audio_mat_id,
                "extra_material_refs": [v_spd_id],
                "source_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                "target_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                "volume": 2.5
            })
            # Phụ đề chữ
            txt_id = uuidv4()
            txt_content = {
                "text": matched_quote["text"],
                "styles": [{
                    "fill": {"content": {"render_type": "solid", "solid": {"color": [1, 1, 1]}}},
                    "font": {"path": FONT_BOLD, "id": ""},
                    "size": 9.0,
                    "shadows": [{
                        "angle": -45,
                        "diffuse": 0.02,
                        "alpha": 0.8,
                        "distance": 5.0,
                        "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                    }],
                    "range": [0, len(matched_quote["text"])]
                }]
            }
            materials["texts"].append({"id": txt_id, "type": "subtitle", "content": json.dumps(txt_content)})
            track_sub["segments"].append({
                "id": uuidv4(),
                "material_id": txt_id,
                "target_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0, "y": -0.404}},
                "visible": True
            })
        else:
            # Chèn B-Roll cắt theo Beat
            if num_broll > 0:
                picked_broll_id = broll_mat_ids[broll_idx % num_broll]
                broll_idx += 1
                spd_id = add_speed()
                cvs_id = add_canvas()
                track_video["segments"].append({
                    "id": uuidv4(),
                    "material_id": picked_broll_id,
                    "extra_material_refs": [spd_id, cvs_id],
                    "source_timerange": {"start": 0, "duration": seg_dur_us},
                    "target_timerange": {"start": seg_start_us, "duration": seg_dur_us},
                    "clip": {"scale": {"x": 1, "y": 1}, "transform": {"x": 0, "y": 0}},
                    "volume": 0.0,
                    "visible": True
                })

    # Thêm BGM Track hoàn chỉnh kèm Beat Markers
    bgm_spd_id = add_speed()
    track_bgm["segments"].append({
        "id": uuidv4(),
        "material_id": bgm_mat_id,
        "extra_material_refs": [bgm_spd_id, beat_mat_id],
        "source_timerange": {"start": 0, "duration": music_duration_us},
        "target_timerange": {"start": 0, "duration": music_duration_us},
        "volume": 0.85
    })

    # Tập hợp các tracks
    tracks = [track_video]
    if track_sub["segments"]:
        tracks.append(track_sub)
    if track_voice["segments"]:
        tracks.append(track_voice)
    tracks.append(track_bgm)

    draft_content = {
        "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
        "color_space": 0,
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "lyrics_sync": True,
            "maintrack_adsorb": True,
            "video_mute": False
        },
        "cover": None,
        "create_time": int(time.time()),
        "duration": music_duration_us,
        "fps": 30.0,
        "id": uuidv4(),
        "materials": materials,
        "name": safe_name,
        "new_version": "128.0.0",
        "platform": {"app_id": 3740, "app_name": "CapCut", "os": "windows"},
        "relationships": [],
        "source": "default",
        "tracks": tracks,
        "update_time": int(time.time()),
        "version": 360000
    }

    # Ghi file draft an toàn
    draft_file = draft_dir / "draft_content.json"
    temp_file = draft_dir / f"draft_content.json.tmp.{int(time.time())}"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, draft_file)

    # 6. Đăng ký vào root_meta_info.json (Vị trí số 1)
    try:
        register_draft.register_project_in_capcut(safe_name)
    except Exception as e:
        logger.warning(f"Lỗi đăng ký root_meta_info: {e}")

    return {
        "ok": True,
        "projectName": safe_name,
        "draftDir": str(draft_dir),
        "durationSec": round(music_duration_us / 1e6, 2),
        "bpm": beat_info.get("bpm"),
        "beatCount": len(beats_us),
        "brollCutsCount": len(track_video["segments"]),
        "tracksCount": len(tracks)
    }

# =====================================================================
# 5. TOÀN TRÌNH: AUTO EDIT & MỞ CAPCUT DESKTOP
# =====================================================================
def run_autoedit(
    music_path: str,
    interview_path: str = "",
    broll_folder: str = "",
    pacing_mode: str = "medium",
    project_name: str = "",
    open_capcut: bool = True
) -> Dict[str, Any]:
    """
    Toàn trình 1-Click:
    1. Biên dịch draft CapCut với Cut-on-Beat và Beat Markers
    2. Khởi động CapCut Desktop và tự động mở thẳng Timeline
    """
    if not project_name:
        project_name = f"AUTOEDIT_{time.strftime('%m%d_%H%M')}"

    logger.info(f"🚀 BẮT ĐẦU AUTOEDIT: Dự án {project_name}")
    logger.info(f"   🎵 Nhạc: {music_path}")
    logger.info(f"   🎙️ Phỏng vấn: {interview_path or 'Không có'}")
    logger.info(f"   🎞️ B-Roll: {broll_folder or 'Không có'}")
    logger.info(f"   ⚡ Nhịp: {pacing_mode}")

    res = build_autoedit_draft(
        project_name=project_name,
        music_path=music_path,
        interview_path=interview_path,
        broll_folder=broll_folder,
        pacing_mode=pacing_mode
    )

    if not res.get("ok"):
        return res

    logger.info(f"✓ Đã tạo xong draft CapCut! BPM: {res.get('bpm')}, Số cuts: {res.get('brollCutsCount')}")

    if open_capcut:
        logger.info("🎬 Đang kích hoạt mở CapCut Desktop...")
        launch_res = capcut_automator.open_project_in_capcut(res["projectName"])
        res["capcutStatus"] = launch_res

    return res

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CapCut AutoEdit Engine")
    parser.add_argument("--music", required=True, help="Đường dẫn file nhạc MP3/WAV")
    parser.add_argument("--interview", default="", help="Đường dẫn video phỏng vấn/VJ")
    parser.add_argument("--broll", default="", help="Đường dẫn thư mục B-Roll")
    parser.add_argument("--pacing", default="medium", choices=["fast", "medium", "cinematic"], help="Nhịp cắt beat")
    parser.add_argument("--name", default="", help="Tên dự án CapCut")
    parser.add_argument("--no-launch", action="store_true", help="Không tự động mở CapCut")

    args = parser.parse_args()
    output = run_autoedit(
        music_path=args.music,
        interview_path=args.interview,
        broll_folder=args.broll,
        pacing_mode=args.pacing,
        project_name=args.name,
        open_capcut=not args.no_launch
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
