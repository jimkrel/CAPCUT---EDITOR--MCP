"""
BBSM_SET3_KB23 - Native CapCut 9.6 Draft Builder
=====================================================
Kịch bản: Tô Kraft BBSM - Đồ ăn mang đi
Cấu trúc: Hybrid A-Roll (Pocket/VJ) + B-Roll (Sony product) theo skill capcut-script-editor
- Track video chính: A-Roll Pocket (VJ nói toàn thời lượng voice)  
- Track B-Roll đè (overlay): Sony clips đè lên đúng từ khóa trong kịch bản
- Track audio voice: vj_voice_kb23.wav (trim chính xác theo timestamp)
- Track BGM: bgm_funky_upbeat.mp3 (ducking 0.25x)
- Track subtitle: Montserrat Bold Shadow -45°, y=-0.404
- Track hook: Banner vàng 0-4.5s
"""

import os
import sys
import json
import time
import shutil
import uuid
from pathlib import Path

BASE_DIR = Path(r"c:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio")
sys.path.insert(0, str(BASE_DIR))

import autoedit_engine

def uuidv4():
    return str(uuid.uuid4()).upper()

# ─── CẤU HÌNH DỰ ÁN ──────────────────────────────────────────────────────────
PROJECT_NAME = "BBSM_SET3_KB23"
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS_DIR = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
DRAFT_DIR = CAPCUT_DRAFTS_DIR / PROJECT_NAME
# Template 1017: project hoạt động chuẩn native CapCut 9.6
REF_DIR = CAPCUT_DRAFTS_DIR / "1017"

# ─── FOOTAGE PATHS ────────────────────────────────────────────────────────────
FOOTAGE_DIR = Path(r"D:\BAO_BI_SAC_MAU_FOOTAGE\KB23")
VOICE_WAV   = FOOTAGE_DIR / "vj_voice_kb23.wav"
BGM_PATH    = FOOTAGE_DIR / "bgm_funky_upbeat.mp3"

# Tìm Pocket A-Roll: file WAV chứa voice VJ (toàn bộ) -> đây chính là VOICE_WAV
# Pocket video: dùng C1701.MP4 làm A-Roll chính (cảnh VJ cầm tô trực diện)
# Sony B-Roll: các clip C17xx, C18xx, C19xx, C20xx (cảnh sản phẩm)

WIN_FONTS = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts" if LOCALAPPDATA else Path()
FONT_BOLD_PATH = str(WIN_FONTS / "Montserrat-Bold.otf").replace("\\", "/")
if not (WIN_FONTS / "Montserrat-Bold.otf").exists():
    FONT_BOLD_PATH = ""  # CapCut sẽ dùng default font

print(f"🎬 KB23 Native Builder v3 - A-Roll/B-Roll Hybrid")
print(f"   Footage: {FOOTAGE_DIR}")
print(f"   Voice:   {VOICE_WAV.name} | exists={VOICE_WAV.exists()}")
print(f"   BGM:     {BGM_PATH.name} | exists={BGM_PATH.exists()}")

# ─── PHÂN TÍCH BEAT BGM ───────────────────────────────────────────────────────
beat_res = autoedit_engine.detect_audio_beats(str(BGM_PATH))
beats_us = beat_res.get("beats_us", [])
bpm      = beat_res.get("bpm", 120)
print(f"   BPM: {bpm:.1f} | Beats: {len(beats_us)}")

# ─── KỊCH BẢN KB23: 10 PHÂN CẢNH ────────────────────────────────────────────
#
# Cấu trúc hybrid theo skill capcut-script-editor:
# - A-Roll: VJ nói (Pocket camera) - chạy LIÊN TỤC làm base video track
# - B-Roll: Sony product clips - đè lên ĐÚNG THỜI ĐIỂM từ khóa xuất hiện
#
# voice_start: thời điểm bắt đầu trong file WAV gốc (giây)
# voice_dur:   độ dài câu thoại (giây)
# broll_clip:  clip Sony B-Roll để đè lên khi VJ nói từ khóa đó
# aroll_source_start: thời điểm cắt trong clip A-Roll Pocket (giây)
#
# Vì chỉ có 1 clip Pocket dài (VJ quay liên tục), ta dùng C1701.MP4 là A-Roll chính,
# source_start tăng dần theo từng scene.
#
# THỰC TẾ: C1701.MP4 là clip Sony (theo tên file). Tuy nhiên theo kịch bản,
# đây là clip VJ ngồi trước tô giấy nói trực tiếp -> dùng làm A-Roll base.
# C1721-C2036 là B-Roll product shots đặc tả sản phẩm.

scenes = [
    {
        # HOOK 0-4s: VJ nói câu dẫn nhập trực tiếp
        "text":             "Anh/chị bán đồ ăn mang đi, muốn tìm tô đựng gọn gàng, in được logo quán",
        "voice_start":      7.0,
        "voice_dur":        4.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",   # A-Roll: VJ cầm tô kraft
        "aroll_src_start":  0.0,
        "broll_clip":       None,                         # Không đè B-Roll - giữ VJ mặt
        "broll_delay":      0.0,   # J-cut delay: B-Roll vào sớm hơn X giây
        "broll_dur":        0.0,
    },
    {
        # 4s-9s: VJ giới thiệu + B-Roll tô đặc tả
        "text":             "Thì có thể tham khảo mẫu tô kraft này, đây cũng là mẫu tô thông dụng đang được nhiều anh chị lựa chọn tại BBSM nha",
        "voice_start":      11.0,
        "voice_dur":        5.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  4.0,
        "broll_clip":       FOOTAGE_DIR / "C1721.MP4",   # B-Roll: cận cảnh tô kraft
        "broll_delay":      1.5,   # J-Cut: B-Roll vào sau 1.5s (VJ nói "mẫu tô kraft" mới đè)
        "broll_dur":        3.5,
    },
    {
        # 9s-13s: Nói về size -> B-Roll show 2 size tô
        "text":             "Loại này có 2 size chính là 750ml và 1000ml",
        "voice_start":      17.0,
        "voice_dur":        4.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  9.0,
        "broll_clip":       FOOTAGE_DIR / "C1751.MP4",   # B-Roll: show 2 size tô
        "broll_delay":      0.5,   # Gần như ngay khi nói "2 size"
        "broll_dur":        3.5,
    },
    {
        # 13s-17s: Liệt kê món ăn -> B-Roll tô có đồ ăn (nguồn khách cung cấp)
        "text":             "Phù hợp cho các món như: mì cay, mì trộn, bún nước tương, salad hay nhiều món ăn nhanh khác",
        "voice_start":      21.0,
        "voice_dur":        4.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  13.0,
        "broll_clip":       FOOTAGE_DIR / "C1781.MP4",   # B-Roll: tô có đồ ăn
        "broll_delay":      0.3,   # Cắt sớm theo kỹ thuật cut-on-noun
        "broll_dur":        3.7,
    },
    {
        # 17s-20s: Đồ khô + đồ nước -> B-Roll đặc tả
        "text":             "Có thể đựng cả đồ khô và đồ nước luôn nha anh/chị",
        "voice_start":      25.0,
        "voice_dur":        3.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  17.0,
        "broll_clip":       FOOTAGE_DIR / "C1821.MP4",   # B-Roll: tô đựng đồ khô/nước
        "broll_delay":      1.0,
        "broll_dur":        2.0,
    },
    {
        # 20s-26s: Chất liệu Kraft -> B-Roll cận quay tô kraft texture
        "text":             "Với chất liệu kraft mang lại cảm giác mộc mạc, nhìn sạch sẽ và chỉn chu khi đóng gói cho khách mang đi",
        "voice_start":      31.0,
        "voice_dur":        6.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  20.0,
        # Bánh kẹp A-B-A: B-Roll đè 4s giữa, đầu và cuối để VJ
        "broll_clip":       FOOTAGE_DIR / "C1861.MP4",   # B-Roll: cận tô kraft
        "broll_delay":      1.5,
        "broll_dur":        4.0,   # Đè 4s giữa câu dài 6s
    },
    {
        # 26s-34s: Nắp PET + nắp PP -> B-Roll cận nắp
        "text":             "Có thể sử dụng nắp PET trong veo với các món đồ lạnh và nắp PP dẻo dai cho món nóng, tuỳ thuộc vào nhu cầu của quán mà anh/chị lựa chọn",
        "voice_start":      46.0,
        "voice_dur":        8.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  26.0,
        "broll_clip":       FOOTAGE_DIR / "C1901.MP4",   # B-Roll: cận nắp PET + PP
        "broll_delay":      1.8,   # VJ nói "nắp PET" -> B-Roll nhảy vào
        "broll_dur":        5.0,
    },
    {
        # 34s-39s: In logo -> B-Roll tô có logo
        "text":             "Đặc biệt, tô kraft này có thể in logo 1 màu, cho quán nào muốn tạo độ nhận diện",
        "voice_start":      58.0,
        "voice_dur":        5.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  34.0,
        "broll_clip":       FOOTAGE_DIR / "C1951.MP4",   # B-Roll: tô in logo
        "broll_delay":      1.0,   # Khi nói "in logo" -> B-Roll
        "broll_dur":        4.0,
    },
    {
        # 39s-42s: Trông chuyên nghiệp -> VJ show tô (A-Roll trực tiếp)
        "text":             "Giúp chiếc tô trông vừa mắt, chuyên nghiệp hơn hẳn",
        "voice_start":      64.0,
        "voice_dur":        3.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  39.0,
        "broll_clip":       FOOTAGE_DIR / "C2001.MP4",   # B-Roll: cận tô nhìn đẹp
        "broll_delay":      0.5,
        "broll_dur":        2.5,
    },
    {
        # 42s-50s: CTA - VJ kết bài trực diện (A-Roll mặt, không đè B-Roll)
        "text":             "Nếu quán mình đang cần mẫu tô kraft tiện lợi, dễ dùng như thế này, thì nhắn ngay BBSM để được hỗ trợ và tư vấn chi tiết hơn nha",
        "voice_start":      68.0,
        "voice_dur":        8.0,
        "aroll_clip":       FOOTAGE_DIR / "C1701.MP4",
        "aroll_src_start":  42.0,
        "broll_clip":       FOOTAGE_DIR / "C2036.MP4",   # B-Roll: showroom, CTA
        "broll_delay":      3.0,   # VJ dẫn vào -> rồi mới show showroom
        "broll_dur":        5.0,
    },
]

# ─── GENERATE UNIQUE IDs ───────────────────────────────────────────────────────
DRAFT_ID   = uuidv4()
PROJECT_ID = uuidv4()
TIMELINE_ID = uuidv4()
print(f"\n   DRAFT_ID:    {DRAFT_ID}")
print(f"   PROJECT_ID:  {PROJECT_ID}")
print(f"   TIMELINE_ID: {TIMELINE_ID}")

# ─── SETUP FOLDER STRUCTURE ───────────────────────────────────────────────────
if DRAFT_DIR.exists():
    shutil.rmtree(DRAFT_DIR)
DRAFT_DIR.mkdir(parents=True, exist_ok=True)

# Copy infrastructure folders từ template 1017
for sd in ["adjust_mask", "common_attachment", "matting", "qr_upload", "Resources", "smart_crop", "subdraft"]:
    src = REF_DIR / sd
    dst = DRAFT_DIR / sd
    if src.exists() and src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.mkdir(parents=True, exist_ok=True)

# Copy config files từ template 1017
for rf in ["attachment_pc_common.json", "draft.extra", "draft_agency_config.json",
           "draft_biz_config.json", "draft_settings", "key_value.json",
           "performance_opt_info.json", "timeline_layout.json", "draft_cover.jpg"]:
    src = REF_DIR / rf
    if src.exists():
        shutil.copy2(src, DRAFT_DIR / rf)

# Timeline folder
TL_DIR = DRAFT_DIR / "Timelines" / TIMELINE_ID
TL_DIR.mkdir(parents=True, exist_ok=True)
(TL_DIR / "attachment").mkdir(exist_ok=True)
(TL_DIR / "common_attachment").mkdir(exist_ok=True)

# Copy timeline support files từ 1017's timeline
REF_TL_DIR = REF_DIR / "Timelines"
ref_tl_id_dirs = [d for d in REF_TL_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')] if REF_TL_DIR.exists() else []
if ref_tl_id_dirs:
    REF_TL = ref_tl_id_dirs[0]
    for tf in ["draft.extra", "attachment_editing.json", "attachment_pc_common.json", "draft_cover.jpg"]:
        src = REF_TL / tf
        if src.exists():
            shutil.copy2(src, TL_DIR / tf)

now_us = int(time.time() * 1_000_000)

# ─── TIMELINES/PROJECT.JSON ───────────────────────────────────────────────────
project_json_data = {
    "config": {
        "color_space": -1,
        "hdr_vivid": False,
        "mixed_track_mode_on": False,
        "render_index_track_mode_on": False,
        "use_float_render": False
    },
    "create_time": now_us,
    "id": PROJECT_ID,
    "main_timeline_id": TIMELINE_ID,
    "timelines": [{
        "create_time": now_us,
        "id": TIMELINE_ID,
        "is_marked_delete": False,
        "name": "Dòng thời gian 01",
        "update_time": now_us
    }],
    "update_time": now_us,
    "version": 0
}
for fname in ["project.json", "project.json.bak"]:
    with open(DRAFT_DIR / "Timelines" / fname, "w", encoding="utf-8") as f:
        json.dump(project_json_data, f, ensure_ascii=False)

# ─── MATERIALS & TRACKS ───────────────────────────────────────────────────────
materials = {
    "videos": [], "audios": [], "texts": [], "speeds": [],
    "canvases": [], "beats": [], "material_animations": [],
    "video_effects": [], "transitions": []
}

def add_speed(val=1.0):
    sid = uuidv4()
    materials["speeds"].append({"id": sid, "mode": 0, "speed": float(val), "type": "speed"})
    return sid

def add_canvas():
    cid = uuidv4()
    materials["canvases"].append({"id": cid, "type": "canvas_color", "color": "#00000000"})
    return cid

def make_video_material(clip_path: Path, has_audio=False):
    """Đăng ký 1 video material, trả về material_id"""
    mid = uuidv4()
    p = str(clip_path.resolve()).replace("\\", "/")
    materials["videos"].append({
        "id": mid,
        "type": "video",
        "path": p,
        "media_path": p,
        "width": 3840,
        "height": 2160,
        "duration": 3_600_000_000,  # 1 giờ dummy, CapCut sẽ đọc từ file
        "has_audio": has_audio,
        "material_name": clip_path.name
    })
    return mid

def make_subtitle_material(text: str):
    """Tạo subtitle material chuẩn Montserrat Bold Shadow"""
    mid = uuidv4()
    content_obj = {
        "text": text,
        "styles": [{
            "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
            "font": {"path": FONT_BOLD_PATH, "id": ""},
            "size": 9.5,
            "bold": True,
            "shadows": [{
                "angle": -45,
                "thickness_projection_angle": -45,
                "thickness_projection_enable": False,
                "diffuse": 0.025,
                "alpha": 0.72,
                "distance": 5.0,
                "content": {"render_type": "solid", "solid": {"color": [0.0, 0.0, 0.0]}}
            }],
            "range": [0, len(text)]
        }]
    }
    materials["texts"].append({
        "id": mid,
        "type": "subtitle",
        "content": json.dumps(content_obj, ensure_ascii=False)
    })
    return mid

# ─── AUDIO MATERIALS ──────────────────────────────────────────────────────────
voice_mat_id = uuidv4()
voice_p = str(VOICE_WAV.resolve()).replace("\\", "/")
materials["audios"].append({
    "id": voice_mat_id, "type": "audio",
    "path": voice_p, "media_path": voice_p,
    "duration": 3_600_000_000,
    "material_name": VOICE_WAV.name
})

bgm_mat_id = uuidv4()
bgm_p = str(BGM_PATH.resolve()).replace("\\", "/")
materials["audios"].append({
    "id": bgm_mat_id, "type": "audio",
    "path": bgm_p, "media_path": bgm_p,
    "duration": 3_600_000_000,
    "material_name": BGM_PATH.name
})

# Beat markers
beat_mat_id = uuidv4()
materials["beats"].append({
    "id": beat_mat_id, "type": "beats",
    "enable_ai_beats": False, "gear": 404, "gear_count": 0, "mode": 404,
    "user_beats": beats_us, "user_delete_ai_beats": None,
    "ai_beats": {"melody_url": "", "melody_path": "", "beats_url": "", "beats_path": "",
                 "melody_percents": [0.0], "beat_speed_infos": []}
})

# ─── TRACKS ───────────────────────────────────────────────────────────────────
# flag=0: main track | flag=1: overlay/subtitle track
track_aroll  = {"id": uuidv4(), "type": "video", "flag": 0, "segments": []}  # A-Roll base (Pocket VJ)
track_broll  = {"id": uuidv4(), "type": "video", "flag": 1, "segments": []}  # B-Roll overlay (Sony product)
track_sub    = {"id": uuidv4(), "type": "text",  "flag": 1, "segments": []}  # Subtitles
track_hook   = {"id": uuidv4(), "type": "text",  "flag": 0, "segments": []}  # Hook banner
track_voice  = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}  # Voice
track_bgm    = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}  # BGM

# ─── ĐĂNG KÝ A-ROLL MATERIALS (MỘT LẦN CHO MỖI CLIP DUY NHẤT) ───────────────
# C1701.MP4 là A-Roll chính duy nhất, đăng ký 1 lần
aroll_main_path = FOOTAGE_DIR / "C1701.MP4"
aroll_mat_id = make_video_material(aroll_main_path, has_audio=False)

# ─── BUILD TIMELINE ───────────────────────────────────────────────────────────
current_us = 0  # vị trí đầu timeline (microseconds)
total_footage_bytes = 0
if VOICE_WAV.exists():
    total_footage_bytes += VOICE_WAV.stat().st_size
if BGM_PATH.exists():
    total_footage_bytes += BGM_PATH.stat().st_size

broll_mat_cache = {}  # clip_path -> mat_id (tránh đăng ký trùng)

for sc in scenes:
    dur_us           = int(round(sc["voice_dur"] * 1_000_000))
    voice_start_us   = int(round(sc["voice_start"] * 1_000_000))
    aroll_src_us     = int(round(sc.get("aroll_src_start", 0.0) * 1_000_000))

    # ── A-Roll segment (Pocket VJ - base video track) ──────────────────────
    spd_a = add_speed(1.0)
    cvs_a = add_canvas()
    track_aroll["segments"].append({
        "id": uuidv4(),
        "material_id": aroll_mat_id,
        "extra_material_refs": [spd_a, cvs_a],
        "source_timerange": {"start": aroll_src_us, "duration": dur_us},
        "target_timerange": {"start": current_us, "duration": dur_us},
        "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}},
        "volume": 0.0,
        "visible": True
    })

    # ── B-Roll overlay (Sony product) - nếu có ─────────────────────────────
    broll_clip = sc.get("broll_clip")
    broll_delay_us = int(round(sc.get("broll_delay", 0.0) * 1_000_000))
    broll_dur_us   = int(round(sc.get("broll_dur", 0.0) * 1_000_000))

    if broll_clip and broll_clip.exists() and broll_dur_us > 0:
        # Đăng ký material nếu chưa có
        key = str(broll_clip)
        if key not in broll_mat_cache:
            broll_mat_cache[key] = make_video_material(broll_clip, has_audio=False)
            total_footage_bytes += broll_clip.stat().st_size
        broll_mid = broll_mat_cache[key]

        spd_b = add_speed(1.0)
        cvs_b = add_canvas()
        broll_start_in_timeline = current_us + broll_delay_us
        # Clamp B-Roll không vượt quá scene duration
        actual_broll_dur = min(broll_dur_us, dur_us - broll_delay_us)
        if actual_broll_dur > 0:
            track_broll["segments"].append({
                "id": uuidv4(),
                "material_id": broll_mid,
                "extra_material_refs": [spd_b, cvs_b],
                "source_timerange": {"start": 0, "duration": actual_broll_dur},
                "target_timerange": {"start": broll_start_in_timeline, "duration": actual_broll_dur},
                "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}},
                "volume": 0.0,
                "visible": True
            })

    # ── Voice Audio segment ─────────────────────────────────────────────────
    spd_v = add_speed(1.0)
    track_voice["segments"].append({
        "id": uuidv4(),
        "material_id": voice_mat_id,
        "extra_material_refs": [spd_v],
        "source_timerange": {"start": voice_start_us, "duration": dur_us},
        "target_timerange": {"start": current_us, "duration": dur_us},
        "volume": 2.8  # Boost DJI Mic
    })

    # ── Subtitle segment ────────────────────────────────────────────────────
    sub_mid = make_subtitle_material(sc["text"])
    track_sub["segments"].append({
        "id": uuidv4(),
        "material_id": sub_mid,
        "target_timerange": {"start": current_us, "duration": dur_us},
        "clip": {"scale": {"x": 0.77, "y": 0.77}, "transform": {"x": 0.0, "y": -0.404}},
        "visible": True
    })

    current_us += dur_us

total_duration_us = current_us

# ─── HOOK BANNER (0 - 4.5s) ──────────────────────────────────────────────────
hook_text = "TÔ KRAFT ĐỰNG ĐỒ ĂN MANG ĐI"
hook_content_obj = {
    "text": hook_text,
    "styles": [{
        "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 0.88, 0.18]}}},  # Gold
        "font": {"path": FONT_BOLD_PATH, "id": ""},
        "size": 11.0,
        "bold": True,
        "shadows": [{
            "angle": -45,
            "thickness_projection_angle": -45,
            "thickness_projection_enable": False,
            "diffuse": 0.025,
            "alpha": 0.85,
            "distance": 5.0,
            "content": {"render_type": "solid", "solid": {"color": [0.0, 0.0, 0.0]}}
        }],
        "range": [0, len(hook_text)]
    }]
}
hook_mat_id = uuidv4()
materials["texts"].append({
    "id": hook_mat_id, "type": "text",
    "content": json.dumps(hook_content_obj, ensure_ascii=False)
})
track_hook["segments"].append({
    "id": uuidv4(),
    "material_id": hook_mat_id,
    "target_timerange": {"start": 0, "duration": 4_500_000},
    "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.35}},
    "visible": True
})

# ─── BGM SEGMENT (toàn bộ timeline) ──────────────────────────────────────────
spd_bgm = add_speed(1.0)
track_bgm["segments"].append({
    "id": uuidv4(),
    "material_id": bgm_mat_id,
    "extra_material_refs": [spd_bgm, beat_mat_id],
    "source_timerange": {"start": 0, "duration": total_duration_us},
    "target_timerange": {"start": 0, "duration": total_duration_us},
    "volume": 0.25  # Ducking: voice rõ hơn BGM
})

# Thứ tự tracks: A-Roll base, B-Roll overlay, voice, BGM, subtitle, hook
tracks = [track_aroll, track_broll, track_voice, track_bgm, track_sub, track_hook]

# ─── PLATFORM INFO (lấy từ máy thực tế) ─────────────────────────────────────
current_platform = {
    "os": "windows",
    "os_version": "10.0.26300",
    "app_id": 359289,
    "app_version": "9.6.0",
    "app_source": "cc",
    "device_id": "612209cf1d1b1487af31c962c9ad8841",
    "hard_disk_id": "",
    "mac_address": "260094fa7ee4b1ee84ffeb93d5742c8f,2555f7cefd05f80d9c72db7c0673e6d2"
}

# ─── DRAFT CONTENT ────────────────────────────────────────────────────────────
draft_content = {
    "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
    "color_space": -1,
    "config": {
        "adjust_max_index": 1, "attachment_info": [], "combination_max_index": 1,
        "export_range": None, "extract_audio_last_index": 1, "hdr_vivid": False,
        "lyrics_recognition_id": "", "lyrics_sync": True, "lyrics_taskinfo": [],
        "maintrack_adsorb": True, "material_save_mode": 0,
        "multi_language_current": "none", "multi_language_list": [],
        "multi_language_main": "none", "multi_language_mode": "none",
        "original_sound_last_index": 1, "record_audio_last_index": 1,
        "sticker_max_index": 1, "subtitle_keywords_config": None,
        "subtitle_recognition_id": "", "subtitle_sync": True, "subtitle_taskinfo": [],
        "system_font_list": [], "use_float_render": False, "video_mute": False,
        "voice_change_sync": False, "zoom_info_params": None
    },
    "cover": None,
    "create_time": 0,
    "duration": total_duration_us,
    "extra_info": None,
    "fps": 30.0,
    "free_render_index_mode_on": False,
    "function_assistant_info": {"fixed_rec_applied": False, "smart_rec_applied": False},
    "group_container": None,
    "id": TIMELINE_ID,
    "is_drop_frame_timecode": False,
    "keyframe_graph_list": [],
    "keyframes": {
        "adjusts": [], "audios": [], "effects": [], "filters": [],
        "handwrites": [], "stickers": [], "texts": [], "videos": []
    },
    "last_modified_platform": current_platform,
    "lyrics_effects": [],
    "materials": materials,
    "mixed_track_mode_on": False,
    "mutable_config": None,
    "name": "",
    "new_version": "189.0.0",
    "path": "",
    "platform": current_platform,
    "relationships": [],
    "render_index_track_mode_on": False,
    "retouch_cover": None,
    "smart_ads_info": None,
    "source": "default",
    "static_cover_image_path": "",
    "time_marks": None,
    "tracks": tracks,
    "uneven_animation_template_info": {"composition": ""},
    "update_time": 0,
    "version": 360000
}

# ─── GHI DRAFT FILES (ĐỒNG BỘ ROOT + TIMELINE) ───────────────────────────────
for target_dir in [DRAFT_DIR, TL_DIR]:
    for fname in ["draft_content.json", "template-2.tmp", "draft_content.json.bak"]:
        with open(target_dir / fname, "w", encoding="utf-8") as f:
            json.dump(draft_content, f, ensure_ascii=False)

print(f"\n✓ draft_content.json: {total_duration_us/1e6:.1f}s | "
      f"{len(materials['videos'])} video mats | "
      f"{len(track_aroll['segments'])} A-Roll segs | "
      f"{len(track_broll['segments'])} B-Roll segs")

# ─── DRAFT META INFO ──────────────────────────────────────────────────────────
# QUAN TRỌNG: draft_fold_path dùng backslash Windows
draft_fold_win = str(DRAFT_DIR).replace("/", "\\")
meta_data = {
    "cloud_draft_cover": False, "cloud_draft_sync": False,
    "cloud_package_completed_time": "",
    "draft_cloud_capcut_purchase_info": "", "draft_cloud_last_action_download": False,
    "draft_cloud_package_type": "", "draft_cloud_purchase_info": "",
    "draft_cloud_template_id": "", "draft_cloud_tutorial_info": "",
    "draft_cloud_videocut_purchase_info": "",
    "draft_cover": "draft_cover.jpg",
    "draft_deeplink_url": "",
    "draft_enterprise_info": {
        "draft_enterprise_extra": "", "draft_enterprise_id": "",
        "draft_enterprise_name": "", "enterprise_material": []
    },
    "draft_fold_path": draft_fold_win,
    "draft_has_unfinished_aigc_video_effect": False,
    "draft_id": DRAFT_ID,
    "draft_is_ae_produce": False, "draft_is_ai_packaging_used": False,
    "draft_is_ai_shorts": False, "draft_is_ai_translate": False,
    "draft_is_article_video_draft": False, "draft_is_cloud_temp_draft": False,
    "draft_is_from_deeplink": "false", "draft_is_infinite_canvas_draft": False,
    "draft_is_invisible": False, "draft_is_pippit_draft": False,
    "draft_is_web_article_video": False,
    "draft_materials": [
        {"type": 0, "value": []}, {"type": 1, "value": []}, {"type": 2, "value": []},
        {"type": 3, "value": []}, {"type": 6, "value": []}, {"type": 7, "value": []},
        {"type": 8, "value": []}
    ],
    "draft_materials_copied_info": [],
    "draft_name": PROJECT_NAME,
    "draft_need_rename_folder": False,
    "draft_new_version": "",
    "draft_removable_storage_device": "",
    # QUAN TRỌNG: draft_root_path dùng backslash Windows
    "draft_root_path": str(CAPCUT_DRAFTS_DIR).replace("/", "\\"),
    "draft_segment_extra_info": [],
    "draft_timeline_materials_size_": total_footage_bytes,
    "draft_type": "",
    "draft_web_article_video_enter_from": "",
    "pippit_avatar_url": "", "pippit_extra_info": "", "pippit_id": "", "pippit_user_name": "",
    "tm_draft_cloud_completed": "", "tm_draft_cloud_entry_id": -1,
    "tm_draft_cloud_modified": 0, "tm_draft_cloud_parent_entry_id": -1,
    "tm_draft_cloud_space_id": -1, "tm_draft_cloud_user_id": -1,
    "tm_draft_create": now_us, "tm_draft_modified": now_us,
    "tm_draft_removed": 0, "tm_duration": total_duration_us
}
with open(DRAFT_DIR / "draft_meta_info.json", "w", encoding="utf-8") as f:
    json.dump(meta_data, f, ensure_ascii=False)

# ─── ROOT META INFO (đăng ký vào vị trí 0) ────────────────────────────────────
root_meta_file = CAPCUT_DRAFTS_DIR / "root_meta_info.json"
with open(root_meta_file, "r", encoding="utf-8") as f:
    root_data = json.load(f)

# QUAN TRỌNG: root entry dùng HOÀN TOÀN forward slash (như CapCut ghi nội bộ)
draft_fold_fwd = str(DRAFT_DIR).replace("\\", "/")
root_entry = {
    "cloud_draft_cover": False, "cloud_draft_sync": False,
    "draft_cloud_last_action_download": False, "draft_cloud_purchase_info": "",
    "draft_cloud_template_id": "", "draft_cloud_tutorial_info": "",
    "draft_cloud_videocut_purchase_info": "",
    "draft_cover": draft_fold_fwd + "/draft_cover.jpg",
    "draft_fold_path": draft_fold_fwd,
    "draft_id": DRAFT_ID,
    "draft_is_ai_shorts": False, "draft_is_cloud_temp_draft": False,
    "draft_is_infinite_canvas_draft": False, "draft_is_invisible": False,
    "draft_is_pippit_draft": False, "draft_is_web_article_video": False,
    "draft_json_file": draft_fold_fwd + "/draft_content.json",  # PURE forward slash!
    "draft_name": PROJECT_NAME, "draft_new_version": "",
    "draft_root_path": str(CAPCUT_DRAFTS_DIR).replace("\\", "/"),
    "draft_timeline_materials_size": total_footage_bytes,
    "draft_type": "", "draft_web_article_video_enter_from": "",
    "pippit_avatar_url": "", "pippit_extra_info": "", "pippit_id": "", "pippit_user_name": "",
    "streaming_edit_draft_ready": True,
    "tm_draft_cloud_completed": "", "tm_draft_cloud_entry_id": -1,
    "tm_draft_cloud_modified": 0, "tm_draft_cloud_parent_entry_id": -1,
    "tm_draft_cloud_space_id": -1, "tm_draft_cloud_user_id": -1,
    "tm_draft_create": now_us, "tm_draft_modified": now_us,
    "tm_draft_removed": 0, "tm_duration": total_duration_us
}

store = root_data.get("all_draft_store", [])
store = [x for x in store if x.get("draft_name") != PROJECT_NAME]
store.insert(0, root_entry)
root_data["all_draft_store"] = store

with open(root_meta_file, "w", encoding="utf-8") as f:
    json.dump(root_data, f, ensure_ascii=False)

print(f"✓ Đăng ký root_meta_info.json vị trí 0 (DRAFT_ID: {DRAFT_ID})")
print(f"\n🎉 KB23 hoàn tất!")
print(f"   Tổng thời lượng: {total_duration_us/1_000_000:.1f}s")
print(f"   A-Roll segments: {len(track_aroll['segments'])}")
print(f"   B-Roll overlays: {len(track_broll['segments'])}")
print(f"   Subtitles:       {len(track_sub['segments'])}")
print(f"\n👉 Mở CapCut -> dự án BBSM_SET3_KB23 sẽ xuất hiện ở đầu danh sách")
