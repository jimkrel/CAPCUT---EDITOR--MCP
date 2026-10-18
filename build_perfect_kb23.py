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
import register_draft
import capcut_automator

def uuidv4():
    return str(uuid.uuid4()).upper()

PROJECT_NAME = "BBSM_SET3_KB23"
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS_DIR = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
DRAFT_DIR = CAPCUT_DRAFTS_DIR / PROJECT_NAME
REF_DIR = CAPCUT_DRAFTS_DIR / "BBSM_SET3_KB22"

print(f"🎬 Khởi tạo dự án chuẩn hóa 100% Native CapCut: {PROJECT_NAME}")

# 1. Đảm bảo thư mục footage sạch D:\BAO_BI_SAC_MAU_FOOTAGE\KB23
CLEAN_DIR = Path(r"D:\BAO_BI_SAC_MAU_FOOTAGE\KB23")
VOICE_WAV = CLEAN_DIR / "vj_voice_kb23.wav"
BGM_PATH = CLEAN_DIR / "bgm_funky_upbeat.mp3"

WIN_FONTS = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts" if LOCALAPPDATA else Path()
FONT_BOLD = str(WIN_FONTS / "Montserrat-Bold.otf").replace("\\", "/") if (WIN_FONTS / "Montserrat-Bold.otf").exists() else "Montserrat-Bold.otf"

# 2. Phân tích beat của bài BGM
beat_res = autoedit_engine.detect_audio_beats(str(BGM_PATH))
beats_us = beat_res.get("beats_us", [])
bpm = beat_res.get("bpm", 120)
print(f"  ✓ BPM: {bpm} | Beats phát hiện: {len(beats_us)}")

# 3. Kịch bản 10 phân cảnh (Voice + B-Roll Sony + Phụ đề)
scenes = [
    {
        "text": "Anh/chị bán đồ ăn mang đi, muốn tìm tô đựng gọn gàng, in được logo quán",
        "voice_start": 7.0,
        "voice_dur": 4.0,
        "clip": CLEAN_DIR / "C1701.MP4"
    },
    {
        "text": "Thì có thể tham khảo mẫu tô kraft này, đây cũng là mẫu tô thông dụng đang được nhiều anh chị lựa chọn tại BBSM nha",
        "voice_start": 11.0,
        "voice_dur": 5.0,
        "clip": CLEAN_DIR / "C1721.MP4"
    },
    {
        "text": "Loại này có 2 size chính là 750ml và 1000ml",
        "voice_start": 17.0,
        "voice_dur": 4.0,
        "clip": CLEAN_DIR / "C1751.MP4"
    },
    {
        "text": "Phù hợp cho các món như: mì cay, mì trộn, bún nước tương, salad hay nhiều món ăn nhanh khác",
        "voice_start": 21.0,
        "voice_dur": 4.0,
        "clip": CLEAN_DIR / "C1781.MP4"
    },
    {
        "text": "Có thể đựng cả đồ khô và đồ nước luôn nha anh/chị",
        "voice_start": 25.0,
        "voice_dur": 3.0,
        "clip": CLEAN_DIR / "C1821.MP4"
    },
    {
        "text": "Với chất liệu kraft mang lại cảm giác mộc mạc, nhìn sạch sẽ và chỉn chu khi đóng gói cho khách mang đi",
        "voice_start": 31.0,
        "voice_dur": 6.0,
        "clip": CLEAN_DIR / "C1861.MP4"
    },
    {
        "text": "Có thể sử dụng nắp PET trong veo với các món đồ lạnh và nắp PP dẻo dai cho món nóng, tuỳ thuộc vào nhu cầu của quán mà anh/chị lựa chọn",
        "voice_start": 46.0,
        "voice_dur": 8.0,
        "clip": CLEAN_DIR / "C1901.MP4"
    },
    {
        "text": "Đặc biệt, tô kraft này có thể in logo 1 màu, cho quán nào muốn tạo độ nhận diện",
        "voice_start": 58.0,
        "voice_dur": 5.0,
        "clip": CLEAN_DIR / "C1951.MP4"
    },
    {
        "text": "Giúp chiếc tô trông vừa mắt, chuyên nghiệp hơn hẳn",
        "voice_start": 64.0,
        "voice_dur": 3.0,
        "clip": CLEAN_DIR / "C2001.MP4"
    },
    {
        "text": "Nếu quán mình đang cần mẫu tô kraft tiện lợi, dễ dùng như thế này, thì nhắn ngay BBSM để được hỗ trợ và tư vấn chi tiết hơn nha",
        "voice_start": 68.0,
        "voice_dur": 8.0,
        "clip": CLEAN_DIR / "C2036.MP4"
    }
]

# 4. Sao chép khung sườn hạ tầng CapCut từ REF_DIR sang DRAFT_DIR
DRAFT_DIR.mkdir(parents=True, exist_ok=True)
SUPPORT_FILES = [
    "attachment_editing.json",
    "attachment_pc_common.json",
    "crypto_key_store.dat",
    "crypto_key_store.dat.bak",
    "draft.extra",
    "draft_agency_config.json",
    "draft_agency_info.json",
    "draft_biz_config.json",
    "draft_virtual_store.json",
    "key_value.json",
    "draft_cover.jpg",
    "draft_settings"
]

for sf in SUPPORT_FILES:
    src_f = REF_DIR / sf
    if src_f.exists():
        dst_f = DRAFT_DIR / sf
        try:
            shutil.copy2(src_f, dst_f)
        except Exception:
            pass

# Cấu trúc Timelines chuẩn CapCut 9.6
TIMELINE_ID = "DFB6AF57-BD90-426A-BAF8-EFE227AF6A8F"
TL_DIR = DRAFT_DIR / "Timelines" / TIMELINE_ID
TL_DIR.mkdir(parents=True, exist_ok=True)

# Copy các file timeline phụ trợ từ REF
REF_TL = REF_DIR / "Timelines" / TIMELINE_ID
if REF_TL.exists():
    for f in REF_TL.iterdir():
        if f.is_file() and f.name not in ["draft_content.json", "template-2.tmp", "draft_content.json.bak", "template.tmp"]:
            try:
                shutil.copy2(f, TL_DIR / f.name)
            except Exception:
                pass

# Copy Timelines/project.json
if (REF_DIR / "Timelines" / "project.json").exists():
    shutil.copy2(REF_DIR / "Timelines" / "project.json", DRAFT_DIR / "Timelines" / "project.json")
if (REF_DIR / "Timelines" / "project.json.bak").exists():
    shutil.copy2(REF_DIR / "Timelines" / "project.json.bak", DRAFT_DIR / "Timelines" / "project.json.bak")

# Xóa các file .tmp hoặc .locked lỗi cũ
for p in [DRAFT_DIR, TL_DIR]:
    for bad in p.glob("*.tmp*"):
        try:
            bad.unlink()
        except Exception:
            pass
    for lock in p.glob(".locked*"):
        try:
            lock.unlink()
        except Exception:
            pass

# 5. Xây dựng materials & tracks
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

def add_speed(val=1.0):
    sid = uuidv4()
    materials["speeds"].append({"id": sid, "mode": 0, "speed": float(val), "type": "speed"})
    return sid

def add_canvas():
    cid = uuidv4()
    materials["canvases"].append({"id": cid, "type": "canvas_color", "color": "#00000000"})
    return cid

# Đăng ký Voice WAV (1 material duy nhất)
voice_mat_id = uuidv4()
voice_path_norm = str(VOICE_WAV.resolve()).replace("\\", "/")
materials["audios"].append({
    "id": voice_mat_id,
    "type": "audio",
    "path": voice_path_norm,
    "media_path": voice_path_norm,
    "duration": 3600000000,
    "material_name": VOICE_WAV.name
})

# Đăng ký BGM (1 material duy nhất)
bgm_mat_id = uuidv4()
bgm_path_norm = str(BGM_PATH.resolve()).replace("\\", "/")
materials["audios"].append({
    "id": bgm_mat_id,
    "type": "audio",
    "path": bgm_path_norm,
    "media_path": bgm_path_norm,
    "duration": 3600000000,
    "material_name": BGM_PATH.name
})

# Đăng ký Beat Markers (Chấm vàng)
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

track_video = {"id": uuidv4(), "type": "video", "flag": 0, "segments": []}
track_sub = {"id": uuidv4(), "type": "text", "flag": 1, "segments": []}
track_hook = {"id": uuidv4(), "type": "text", "flag": 0, "segments": []}
track_voice = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}
track_bgm = {"id": uuidv4(), "type": "audio", "flag": 0, "segments": []}

current_timeline_us = 0

for sc in scenes:
    dur_us = int(round(sc["voice_dur"] * 1e6))
    voice_start_us = int(round(sc["voice_start"] * 1e6))
    clip_path = str(sc["clip"].resolve()).replace("\\", "/")

    # Video Material
    v_mat_id = uuidv4()
    materials["videos"].append({
        "id": v_mat_id,
        "type": "video",
        "path": clip_path,
        "media_path": clip_path,
        "width": 3840,
        "height": 2160,
        "duration": 3600000000,
        "has_audio": False,
        "material_name": sc["clip"].name
    })

    spd_id = add_speed()
    cvs_id = add_canvas()

    # Video Segment
    track_video["segments"].append({
        "id": uuidv4(),
        "material_id": v_mat_id,
        "extra_material_refs": [spd_id, cvs_id],
        "source_timerange": {"start": 0, "duration": dur_us},
        "target_timerange": {"start": current_timeline_us, "duration": dur_us},
        "clip": {"scale": {"x": 1, "y": 1}, "transform": {"x": 0, "y": 0}},
        "volume": 0.0,
        "visible": True
    })

    # Voice Audio Segment
    v_spd_id = add_speed()
    track_voice["segments"].append({
        "id": uuidv4(),
        "material_id": voice_mat_id,
        "extra_material_refs": [v_spd_id],
        "source_timerange": {"start": voice_start_us, "duration": dur_us},
        "target_timerange": {"start": current_timeline_us, "duration": dur_us},
        "volume": 2.8 # Boost DJI Mic
    })

    # Subtitle Segment (Montserrat Bold Shadow y = -0.404 Safe Zone)
    txt_id = uuidv4()
    txt_content = {
        "text": sc["text"],
        "styles": [{
            "fill": {"content": {"render_type": "solid", "solid": {"color": [1, 1, 1]}}},
            "font": {"path": FONT_BOLD, "id": ""},
            "size": 9.5,
            "bold": True,
            "shadows": [{
                "angle": -45,
                "diffuse": 0.02,
                "alpha": 0.8,
                "distance": 5.0,
                "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
            }],
            "range": [0, len(sc["text"])]
        }]
    }
    materials["texts"].append({"id": txt_id, "type": "subtitle", "content": json.dumps(txt_content)})
    track_sub["segments"].append({
        "id": uuidv4(),
        "material_id": txt_id,
        "target_timerange": {"start": current_timeline_us, "duration": dur_us},
        "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0, "y": -0.404}},
        "visible": True
    })

    current_timeline_us += dur_us

total_duration_us = current_timeline_us

# Hook Banner (0 - 4.5s)
hook_mat_id = uuidv4()
hook_text = "TÔ KRAFT ĐỰNG ĐỒ ĂN MANG ĐI"
hook_content = {
    "text": hook_text,
    "styles": [{
        "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 0.88, 0.18]}}}, # Gold
        "font": {"path": FONT_BOLD, "id": ""},
        "size": 11.0,
        "bold": True,
        "shadows": [{
            "angle": -45,
            "diffuse": 0.025,
            "alpha": 0.85,
            "distance": 5.0,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
        }],
        "range": [0, len(hook_text)]
    }]
}
materials["texts"].append({"id": hook_mat_id, "type": "text", "content": json.dumps(hook_content)})
track_hook["segments"].append({
    "id": uuidv4(),
    "material_id": hook_mat_id,
    "target_timerange": {"start": 0, "duration": 4500000},
    "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0, "y": 0.35}},
    "visible": True
})

# BGM Segment
bgm_spd_id = add_speed()
track_bgm["segments"].append({
    "id": uuidv4(),
    "material_id": bgm_mat_id,
    "extra_material_refs": [bgm_spd_id, beat_mat_id],
    "source_timerange": {"start": 0, "duration": total_duration_us},
    "target_timerange": {"start": 0, "duration": total_duration_us},
    "volume": 0.28 # Ducking
})

tracks = [track_video, track_sub, track_hook, track_voice, track_bgm]

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
    "duration": total_duration_us,
    "fps": 30.0,
    "id": TIMELINE_ID,
    "materials": materials,
    "name": PROJECT_NAME,
    "new_version": "128.0.0",
    "platform": {"app_id": 3740, "app_name": "CapCut", "os": "windows"},
    "relationships": [],
    "source": "default",
    "tracks": tracks,
    "update_time": int(time.time()),
    "version": 360000
}

# 6. Ghi đồng bộ cả 2 tầng: DRAFT_DIR và Timelines
for target_dir in [DRAFT_DIR, TL_DIR]:
    draft_file = target_dir / "draft_content.json"
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)
    # Ghi template-2.tmp khớp 100%
    tmp2_file = target_dir / "template-2.tmp"
    with open(tmp2_file, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)
    # Ghi draft_content.json.bak
    bak_file = target_dir / "draft_content.json.bak"
    with open(bak_file, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False, indent=2)

print(f"✓ Đã ghi đồng bộ draft_content.json & template-2.tmp: {total_duration_us/1e6:.1f}s")

# 7. Cập nhật draft_meta_info.json với định dạng sạch tuyệt đối
meta_file = DRAFT_DIR / "draft_meta_info.json"
now_us = int(time.time() * 1_000_000)
meta_data = {
    "cloud_draft_cover": False,
    "cloud_draft_sync": False,
    "draft_cloud_last_action_download": True,
    "draft_cover": "draft_cover.jpg",
    "draft_fold_path": str(DRAFT_DIR).replace("\\", "/"),
    "draft_id": TIMELINE_ID,
    "draft_is_ai_shorts": False,
    "draft_is_cloud_temp_draft": False,
    "draft_is_infinite_canvas_draft": False,
    "draft_is_invisible": False,
    "draft_is_pippit_draft": False,
    "draft_is_web_article_video": False,
    "draft_name": PROJECT_NAME,
    "draft_new_version": "164.0.0",
    "draft_root_path": str(CAPCUT_DRAFTS_DIR).replace("\\", "/"),
    "draft_timeline_materials_size_": 1422354538,
    "draft_type": "",
    "draft_web_article_video_enter_from": "",
    "tm_draft_create": now_us,
    "tm_draft_modified": now_us,
    "tm_draft_removed": 0,
    "tm_duration": total_duration_us
}
with open(meta_file, "w", encoding="utf-8") as f:
    json.dump(meta_data, f, ensure_ascii=False, indent=2)

# 8. Cập nhật root_meta_info.json (Vị trí số 1)
root_meta_file = CAPCUT_DRAFTS_DIR / "root_meta_info.json"
with open(root_meta_file, "r", encoding="utf-8") as f:
    root_data = json.load(f)

draft_dir_norm = str(DRAFT_DIR).replace("\\", "/")
root_dir_norm = str(CAPCUT_DRAFTS_DIR).replace("\\", "/")

root_entry = {
    "cloud_draft_cover": False,
    "cloud_draft_sync": False,
    "draft_cloud_last_action_download": True,
    "draft_cloud_purchase_info": "{\n}\n",
    "draft_cloud_template_id": "",
    "draft_cloud_tutorial_info": "{\n}\n",
    "draft_cloud_videocut_purchase_info": "{\"template_type\":\"\",\"unlock_type\":\"\"}",
    "draft_cover": f"{draft_dir_norm}/draft_cover.jpg",
    "draft_fold_path": draft_dir_norm,
    "draft_id": TIMELINE_ID,
    "draft_is_ai_shorts": False,
    "draft_is_cloud_temp_draft": False,
    "draft_is_infinite_canvas_draft": False,
    "draft_is_invisible": False,
    "draft_is_pippit_draft": False,
    "draft_is_web_article_video": False,
    "draft_json_file": f"{draft_dir_norm}/draft_content.json",
    "draft_name": PROJECT_NAME,
    "draft_new_version": "164.0.0",
    "draft_root_path": root_dir_norm,
    "draft_timeline_materials_size": 1422354538,
    "draft_type": "",
    "draft_web_article_video_enter_from": "",
    "pippit_avatar_url": "",
    "pippit_extra_info": "",
    "pippit_id": "",
    "pippit_user_name": "",
    "streaming_edit_draft_ready": True,
    "tm_draft_cloud_completed": "",
    "tm_draft_cloud_entry_id": -1,
    "tm_draft_cloud_modified": 0,
    "tm_draft_cloud_parent_entry_id": -1,
    "tm_draft_cloud_space_id": 0,
    "tm_draft_cloud_user_id": 0,
    "tm_draft_create": now_us,
    "tm_draft_modified": now_us,
    "tm_draft_removed": 0,
    "tm_duration": total_duration_us
}

store = root_data.get("all_draft_store", [])
store = [x for x in store if x.get("draft_name") != PROJECT_NAME]
store.insert(0, root_entry)
root_data["all_draft_store"] = store

with open(root_meta_file, "w", encoding="utf-8") as f:
    json.dump(root_data, f, ensure_ascii=False, indent=2)

print("✓ Đã đăng ký BBSM_SET3_KB23 lên vị trí số 1 trong root_meta_info.json")
print("🎉 Hoàn tất cấu trúc dự án! Không còn bất kỳ đường dẫn lỗi hay ký tự bất thường nào.")
