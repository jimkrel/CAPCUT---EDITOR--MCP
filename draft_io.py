import os
import json
import re
import uuid
import shutil
import logging
from pathlib import Path
import psutil

# Thiết lập Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Tự động dò đường dẫn lưu trữ CapCut Draft
def detect_capcut_draft_base() -> Path:
    env_dir = os.environ.get("CAPCUT_DRAFTS_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p

    candidates = [
        Path.home() / "AppData/Local/CapCut/User Data/Projects/com.lveditor.draft",
        Path.home() / "AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft",
        Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft",
        Path.home() / "Movies/JianyingPro/User Data/Projects/com.lveditor.draft",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

CAPCUT_DRAFT_BASE = detect_capcut_draft_base()

def is_capcut_running() -> bool:
    target_names = ["capcut.exe", "jianyingpro.exe", "capcut", "jianying"]
    for proc in psutil.process_iter(['name']):
        try:
            name = (proc.info.get('name') or '').lower()
            if any(t in name for t in target_names):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def check_capcut_not_running():
    if is_capcut_running():
        raise RuntimeError("Phần mềm CapCut/JianYing đang chạy. Vui lòng đóng ứng dụng để tránh xung đột ghi đè.")

def get_draft_file(project_name: str) -> Path:
    if not re.match(r"^[\w\- .]+$", project_name):
        raise ValueError("Tên dự án chứa ký tự không hợp lệ")
    draft_file = (CAPCUT_DRAFT_BASE / project_name / "draft_content.json").resolve()
    base_resolved = CAPCUT_DRAFT_BASE.resolve()
    if not (draft_file == base_resolved or base_resolved in draft_file.parents):
        raise ValueError("Đường dẫn dự án nằm ngoài phạm vi cho phép")
    if not draft_file.exists():
        raise FileNotFoundError(f"Dự án '{project_name}' không tồn tại")
    return draft_file

def save_draft_with_history(draft_file: Path, data: dict):
    history_dir = draft_file.parent / ".history"
    history_dir.mkdir(exist_ok=True)
    
    # Snapshot 0 ban đầu nếu history rỗng
    existing_snaps = sorted(history_dir.glob("draft_*.json"), key=os.path.getmtime)
    if not existing_snaps and draft_file.exists():
        try:
            shutil.copy2(draft_file, history_dir / "draft_000_init.json")
        except Exception as e:
            logging.warning(f"Không thể tạo initial snapshot: {e}")

    # Ghi snapshot mới
    timestamp = uuid.uuid4().hex[:8]
    snap_file = history_dir / f"draft_{timestamp}.json"
    try:
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # Giữ tối đa 20 snapshot gần nhất
        snaps = sorted(history_dir.glob("draft_*.json"), key=os.path.getmtime)
        if len(snaps) > 20:
            for old_snap in snaps[:-20]:
                try:
                    old_snap.unlink()
                except Exception:
                    pass
    except Exception as e:
        logging.warning(f"Không thể lưu history snapshot: {e}")
        
    # Backup an toàn draft trước khi ghi đè
    backup_path = draft_file.with_suffix(".json.bak")
    if draft_file.exists():
        shutil.copy2(draft_file, backup_path)
        
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def recalculate_project_duration(data: dict):
    max_us = 0
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            tr = s.get("target_timerange") or {}
            end = tr.get("start", 0) + tr.get("duration", 0)
            if end > max_us:
                max_us = end
    data["duration"] = max_us
    return max_us

def clean_orphan_materials(data: dict):
    referenced_ids = set()
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            mid = s.get("material_id")
            if mid:
                referenced_ids.add(mid)
            for ref in (s.get("extra_material_refs") or []):
                referenced_ids.add(ref)
                
    materials = data.get("materials") or {}
    for mat_cat, items in list(materials.items()):
        if isinstance(items, list):
            materials[mat_cat] = [item for item in items if item.get("id") in referenced_ids]

def resolve_draft_path(raw_path: str, draft_dir: Path) -> str:
    if not raw_path:
        return ""
    if "{draft_folder}" in raw_path:
        rel = raw_path.replace("{draft_folder}/", "").replace("{draft_folder}\\", "")
        return str(draft_dir / rel)
    p = Path(raw_path)
    if p.is_absolute() and p.exists():
        return str(p)
    if not p.is_absolute():
        candidate = draft_dir / raw_path
        if candidate.exists():
            return str(candidate)
    return raw_path

def get_project_dict(project_name: str) -> dict:
    draft_file = get_draft_file(project_name)
    draft_dir = draft_file.parent
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    duration_us = data.get("duration", 0)
    fps = data.get("fps", 30)
    tracks_raw = data.get("tracks", [])
    materials = data.get("materials", {})
    
    texts_map = {}
    for t in materials.get("texts", []):
        try:
            content_obj = json.loads(t.get("content", "{}"))
            texts_map[t.get("id")] = {
                "text": content_obj.get("text", ""),
                "styles": content_obj.get("styles", []),
                "raw": t
            }
        except Exception:
            texts_map[t.get("id")] = {"text": "", "styles": [], "raw": t}
            
    stickers_map = {s.get("id"): s for s in materials.get("stickers", [])}
    videos_map = {}
    for v in materials.get("videos", []):
        vid = v.get("id")
        raw_path = v.get("path", "") or v.get("media_path", "")
        resolved = resolve_draft_path(raw_path, draft_dir)
        videos_map[vid] = {**v, "_resolved_path": resolved}
        
    audios_map = {}
    for a in materials.get("audios", []):
        aid = a.get("id")
        raw_path = a.get("path", "") or a.get("media_path", "")
        resolved = resolve_draft_path(raw_path, draft_dir)
        audios_map[aid] = {**a, "_resolved_path": resolved}
        
    speeds_map = {s.get("id"): s for s in materials.get("speeds", [])}
    
    parsed_tracks = []
    max_track_end = 0
    for t_idx, track in enumerate(tracks_raw):
        track_type = track.get("type", "video")
        parsed_segments = []
        for s in track.get("segments", []):
            try:
                trange = s.get("target_timerange") or {}
                start_us = trange.get("start", 0)
                dur_us = trange.get("duration", 0)
                end_us = start_us + dur_us
                if end_us > max_track_end:
                    max_track_end = end_us
                    
                mid = s.get("material_id")
                clip_obj = s.get("clip") or {}
                scale_obj = clip_obj.get("scale") or {}
                transform_obj = clip_obj.get("transform") or {}
                
                seg_info = {
                    "id": s.get("id"),
                    "material_id": mid,
                    "start_us": start_us,
                    "duration_us": dur_us,
                    "end_us": end_us,
                    "type": track_type,
                    "label": "Clip",
                    "color": "#2563eb",
                    "scale": scale_obj.get("x", 1.0),
                    "transform_x": transform_obj.get("x", 0.0),
                    "transform_y": transform_obj.get("y", 0.0),
                    "media_path": "",
                    "effects": [],
                    "animations": [],
                    "visible": s.get("visible", True),
                    "volume": s.get("volume", 1.0),
                    "speed": 1.0,
                    "details": {}
                }
                
                for ref_id in (s.get("extra_material_refs") or []):
                    if ref_id in speeds_map:
                        seg_info["speed"] = speeds_map[ref_id].get("speed", 1.0)
                        
                if track_type == "text":
                    t_info = texts_map.get(mid) or {}
                    seg_info["label"] = t_info.get("text", "Văn bản") or "Văn bản trống"
                    seg_info["color"] = "#6366f1"
                    seg_info["details"]["text"] = t_info.get("text", "")
                elif track_type == "sticker":
                    st_obj = stickers_map.get(mid) or {}
                    seg_info["label"] = st_obj.get("name", "Sticker") or "Ảnh vector"
                    seg_info["color"] = "#d97706"
                elif track_type == "video":
                    v_obj = videos_map.get(mid) or {}
                    resolved = v_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else ""
                    seg_info["label"] = filename or "Video Clip"
                    seg_info["color"] = "#2563eb"
                    seg_info["media_path"] = resolved
                    seg_info["details"]["path"] = resolved
                elif track_type == "audio":
                    a_obj = audios_map.get(mid) or {}
                    resolved = a_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else ""
                    seg_info["label"] = filename or "Audio"
                    seg_info["color"] = "#0d9488"
                    seg_info["media_path"] = resolved
                    seg_info["details"]["path"] = resolved
                elif track_type in ("effect", "adjust"):
                    seg_info["label"] = "Hiệu ứng"
                    seg_info["color"] = "#db2777"
                    
                parsed_segments.append(seg_info)
            except Exception as seg_err:
                logging.warning(f"Lỗi parse segment {s.get('id')}: {seg_err}")
                tr_fallback = s.get("target_timerange") or {}
                f_start = tr_fallback.get("start", 0)
                f_dur = tr_fallback.get("duration", 0)
                f_end = f_start + f_dur
                type_labels = {
                    "video": "Video Clip",
                    "audio": "Audio",
                    "text": "Văn bản",
                    "effect": "Hiệu ứng",
                    "adjust": "Hiệu ứng",
                    "sticker": "Nhãn dán"
                }
                fallback_label = type_labels.get(track_type, "Clip")
                fallback_color = "#2563eb" if track_type == "video" else ("#0d9488" if track_type == "audio" else "#d97706")
                parsed_segments.append({
                    "id": s.get("id", "?"),
                    "material_id": s.get("material_id", ""),
                    "start_us": f_start,
                    "duration_us": f_dur,
                    "end_us": f_end,
                    "type": track_type,
                    "label": fallback_label,
                    "color": fallback_color,
                    "scale": 1.0, "transform_x": 0, "transform_y": 0,
                    "media_path": "", "effects": [], "animations": [],
                    "visible": True, "volume": 1.0, "speed": 1.0, "details": {}
                })
                
        track_flag = track.get("flag", 0)
        is_main_track = (track_type == "video" and track_flag == 0)
        
        parsed_tracks.append({
            "index": t_idx,
            "id": track.get("id"),
            "type": track_type,
            "flag": track_flag,
            "is_main": is_main_track,
            "muted": False,
            "locked": False,
            "hidden": False,
            "segments": parsed_segments
        })
        
    v_count, a_count, t_count, fx_count, st_count = 1, 1, 1, 1, 1
    for pt in parsed_tracks:
        ttype = pt["type"]
        if ttype == "video":
            if pt["is_main"]:
                pt["label"] = "V1 (Chính)"
            else:
                v_count += 1
                pt["label"] = f"V{v_count} (Lớp phủ)"
        elif ttype == "audio":
            if pt["flag"] == 1 or len([s for s in pt["segments"] if s["duration_us"] > 20_000_000]) > 0:
                pt["label"] = f"A{a_count} (BGM/Nhạc)"
            else:
                pt["label"] = f"A{a_count} (Thoại)"
            a_count += 1
        elif ttype == "text":
            pt["label"] = f"T{t_count} (Phụ đề)"
            t_count += 1
        elif ttype in ("adjust", "effect"):
            pt["label"] = f"FX{fx_count} (Hiệu ứng)"
            fx_count += 1
        elif ttype == "sticker":
            pt["label"] = f"ST{st_count} (Nhãn dán)"
            st_count += 1
        else:
            pt["label"] = f"Track {pt['index'] + 1}"
            
    calc_duration = max(duration_us, max_track_end)
    
    all_components = []
    for t in parsed_tracks:
        for s in t.get("segments", []):
            all_components.append({
                "id": s["id"],
                "material_id": s.get("material_id"),
                "track_index": t["index"],
                "track_type": t["type"],
                "type": s["type"],
                "label": s["label"],
                "start_us": s["start_us"],
                "duration_us": s["duration_us"],
                "end_us": s["end_us"],
                "media_path": s.get("media_path", ""),
                "scale": s.get("scale", 1.0),
                "volume": s.get("volume", 1.0),
                "speed": s.get("speed", 1.0),
                "effects": s.get("effects", []),
                "animations": s.get("animations", []),
                "details": s.get("details", {})
            })

    canvas_config = data.get("canvas_config") or {}
    color_space = data.get("color_space") or canvas_config.get("color_space") or "Rec. 709"

    return {
        "project_name": project_name,
        "path": str(draft_file).replace("\\", "/"),
        "duration_us": calc_duration,
        "fps": fps,
        "color_space": color_space,
        "canvas_config": canvas_config,
        "tracks": parsed_tracks,
        "components": all_components,
        "raw_stats": {
            "track_count": len(tracks_raw),
            "text_count": len(materials.get("texts", [])),
            "video_count": len(materials.get("videos", [])),
            "audio_count": len(materials.get("audios", [])),
            "transition_count": len(materials.get("transitions", [])),
            "effect_count": len(materials.get("video_effects", [])),
            "sticker_count": len(materials.get("stickers", []))
        }
    }

def list_all_projects_data() -> dict:
    if not CAPCUT_DRAFT_BASE.exists():
        return {
            "projects": [],
            "warning": f"Không tìm thấy thư mục CapCut tại: {CAPCUT_DRAFT_BASE}."
        }
    projects = []
    for item in CAPCUT_DRAFT_BASE.iterdir():
        draft_file = item / "draft_content.json"
        if item.is_dir() and draft_file.exists():
            mtime = os.path.getmtime(draft_file)
            video_count, text_count, duration_us = 0, 0, 0
            err_msg = None
            try:
                with open(draft_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    mats = meta.get("materials") or {}
                    video_count = len(mats.get("videos") or [])
                    text_count = len(mats.get("texts") or [])
                    duration_us = meta.get("duration", 0)
            except json.JSONDecodeError:
                err_msg = "Không parse được JSON, có thể draft bị mã hóa hoặc hỏng"
            except Exception as e:
                err_msg = f"Lỗi đọc draft: {str(e)}"
                
            projects.append({
                "name": item.name,
                "path": str(draft_file).replace("\\", "/"),
                "modified": mtime,
                "has_footage": video_count > 0,
                "video_count": video_count,
                "text_count": text_count,
                "duration_sec": round(duration_us / 1e6, 2),
                "error": err_msg
            })
    projects.sort(key=lambda x: x["modified"], reverse=True)
    return {"projects": projects}

def update_clip_op(project_name: str, segment_id: str, start_us: int = None, duration_us: int = None, scale: float = None, speed: float = None, volume: float = None, text_content: str = None) -> dict:
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    target_mid = None
    target_seg = None
    target_track = None
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            if s.get("id") == segment_id:
                target_seg = s
                target_mid = s.get("material_id")
                target_track = track
                break
        if target_seg:
            break
        
    if not target_seg or not target_track:
        raise ValueError("Segment not found")
        
    cur_trange = target_seg.get("target_timerange") or {}
    cur_start = cur_trange.get("start", 0)
    cur_dur = cur_trange.get("duration", 0)
    new_start = max(0, start_us) if start_us is not None else cur_start
    new_dur = max(100_000, duration_us) if duration_us is not None else cur_dur
    new_end = new_start + new_dur

    for other in target_track.get("segments", []):
        if other.get("id") == segment_id:
            continue
        o_tr = other.get("target_timerange") or {}
        o_start = o_tr.get("start", 0)
        o_dur = o_tr.get("duration", 0)
        o_end = o_start + o_dur
        if max(new_start, o_start) < min(new_end, o_end):
            overlap_us = min(new_end, o_end) - max(new_start, o_start)
            if overlap_us <= 500_000:
                if new_start < o_start:
                    new_dur = max(100_000, o_start - new_start)
                    new_end = new_start + new_dur
                else:
                    new_start = o_end
                    new_end = new_start + new_dur
            else:
                raise ValueError("Clip bị chồng chéo với clip khác trong cùng track")

    if "target_timerange" not in target_seg:
        target_seg["target_timerange"] = {}
    target_seg["target_timerange"]["start"] = new_start
    target_seg["target_timerange"]["duration"] = new_dur

    speed_val = target_seg.get("speed", 1.0) or 1.0
    if speed is not None:
        speed_val = max(0.1, min(10.0, speed))
        target_seg["speed"] = speed_val
        mats = data.setdefault("materials", {})
        speeds_list = mats.setdefault("speeds", [])
        speed_ref_id = None
        for ref_id in (target_seg.get("extra_material_refs") or []):
            for sp in speeds_list:
                if sp.get("id") == ref_id:
                    sp["speed"] = speed_val
                    speed_ref_id = ref_id
                    break
            if speed_ref_id:
                break
        if not speed_ref_id:
            speed_ref_id = str(uuid.uuid4()).upper()
            speeds_list.append({"id": speed_ref_id, "speed": speed_val, "type": "speed"})
            if "extra_material_refs" not in target_seg:
                target_seg["extra_material_refs"] = []
            target_seg["extra_material_refs"].append(speed_ref_id)

    if target_seg.get("source_timerange"):
        target_seg["source_timerange"]["duration"] = int(round(new_dur * speed_val))

    if scale is not None:
        target_seg["clip"] = target_seg.get("clip") or {}
        target_seg["clip"]["scale"] = {"x": scale, "y": scale}
    if volume is not None:
        target_seg["volume"] = max(0.0, min(2.0, volume))
        
    if text_content is not None and target_mid:
        for t in data.get("materials", {}).get("texts", []):
            if t.get("id") == target_mid:
                c_obj = json.loads(t.get("content", "{}"))
                c_obj["text"] = text_content
                t["content"] = json.dumps(c_obj, ensure_ascii=False)
                break
                
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
    return {"status": "success", "message": "Clip updated successfully"}

def split_clip_op(project_name: str, target_segment_id: str, playhead_time_us: int) -> dict:
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    split_us = playhead_time_us or 0
    found = False
    materials = data.setdefault("materials", {})
    
    for track in data.get("tracks", []):
        for idx, s in enumerate(track.get("segments", [])):
            if s.get("id") == target_segment_id:
                tr = s.get("target_timerange") or {}
                start = tr.get("start", 0)
                dur = tr.get("duration", 0)
                end = start + dur
                if start < split_us < end:
                    left_dur = split_us - start
                    right_dur = end - split_us
                    tr["duration"] = left_dur
                    
                    new_seg = json.loads(json.dumps(s))
                    new_seg["id"] = str(uuid.uuid4()).upper()
                    if "target_timerange" not in new_seg:
                        new_seg["target_timerange"] = {}
                    new_seg["target_timerange"]["start"] = split_us
                    new_seg["target_timerange"]["duration"] = right_dur
                    
                    if s.get("source_timerange"):
                        speed = s.get("speed", 1.0) or 1.0
                        src_start = s["source_timerange"].get("start", 0)
                        src_dur = s["source_timerange"].get("duration", 0)
                        left_src_dur = int(round(left_dur * speed))
                        s["source_timerange"]["duration"] = left_src_dur
                        if "source_timerange" not in new_seg:
                            new_seg["source_timerange"] = {}
                        new_seg["source_timerange"]["start"] = src_start + left_src_dur
                        new_seg["source_timerange"]["duration"] = max(100_000, src_dur - left_src_dur)
                        
                    new_extra_refs = []
                    for ref_id in (s.get("extra_material_refs") or []):
                        new_ref_id = str(uuid.uuid4()).upper()
                        cloned = False
                        for mat_cat in ["video_effects", "material_animations", "speeds", "transitions", "stickers"]:
                            cat_list = materials.get(mat_cat) or []
                            for mat_item in cat_list:
                                if mat_item.get("id") == ref_id:
                                    cloned_item = json.loads(json.dumps(mat_item))
                                    cloned_item["id"] = new_ref_id
                                    cat_list.append(cloned_item)
                                    new_extra_refs.append(new_ref_id)
                                    cloned = True
                                    break
                            if cloned:
                                break
                    new_seg["extra_material_refs"] = new_extra_refs
                    
                    keyframes = s.get("keyframe_list") or []
                    if keyframes:
                        left_kfs = []
                        right_kfs = []
                        for kf in keyframes:
                            kf_time = kf.get("time_offset", 0)
                            if kf_time <= left_dur:
                                left_kfs.append(kf)
                            else:
                                new_kf = json.loads(json.dumps(kf))
                                new_kf["time_offset"] = kf_time - left_dur
                                right_kfs.append(new_kf)
                        s["keyframe_list"] = left_kfs
                        new_seg["keyframe_list"] = right_kfs
                        
                    track["segments"].insert(idx + 1, new_seg)
                    found = True
                    break
        if found:
            break
            
    if not found:
        raise ValueError("Không tìm thấy clip hoặc điểm cắt không nằm trong clip")
        
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
    return {"status": "success", "message": "Split clip successfully"}

def delete_clip_op(project_name: str, target_segment_id: str) -> dict:
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    found = False
    for track in data.get("tracks", []):
        segs = track.get("segments", [])
        for idx, s in enumerate(segs):
            if s.get("id") == target_segment_id:
                segs.pop(idx)
                found = True
                break
        if found:
            break
            
    if not found:
        raise ValueError("Segment not found")
        
    recalculate_project_duration(data)
    clean_orphan_materials(data)
    save_draft_with_history(draft_file, data)
    return {"status": "success", "message": "Clip deleted successfully"}

def undo_project_op(project_name: str) -> dict:
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    history_dir = draft_file.parent / ".history"
    if not history_dir.exists():
        raise ValueError("Chưa có lịch sử thao tác để hoàn tác")
        
    snaps = sorted(history_dir.glob("draft_*.json"), key=os.path.getmtime)
    if len(snaps) < 2:
        raise ValueError("Đã ở phiên bản ban đầu nhất")
        
    redo_dir = draft_file.parent / ".redo"
    redo_dir.mkdir(exist_ok=True)
    latest_snap = snaps[-1]
    shutil.move(str(latest_snap), str(redo_dir / latest_snap.name))
    
    prev_snap = snaps[-2]
    with open(prev_snap, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": "Hoàn tác thành công", "remaining_history": len(snaps) - 1}

def redo_project_op(project_name: str) -> dict:
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    redo_dir = draft_file.parent / ".redo"
    if not redo_dir.exists():
        raise ValueError("Không có lịch sử làm lại")
        
    redo_snaps = sorted(redo_dir.glob("draft_*.json"), key=os.path.getmtime)
    if not redo_snaps:
        raise ValueError("Không có thao tác nào để làm lại")
        
    target_snap = redo_snaps[-1]
    history_dir = draft_file.parent / ".history"
    history_dir.mkdir(exist_ok=True)
    shutil.move(str(target_snap), str(history_dir / target_snap.name))
    
    with open(history_dir / target_snap.name, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": "Làm lại thành công"}

# Aliases for consistent naming
list_projects_core = list_all_projects_data
get_project_core = get_project_dict
split_clip_core = split_clip_op
update_clip_core = update_clip_op
delete_clip_core = delete_clip_op

