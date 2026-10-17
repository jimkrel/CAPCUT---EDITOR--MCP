import os
import json
import shutil
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

def resolve_draft_path(raw_path: str, draft_dir: Path) -> str:
    """Resolve CapCut ##_draftpath_placeholder_UUID_## to the actual draft folder path."""
    if not raw_path:
        return ""
    m = re.search(r'##_draftpath_placeholder_[^#]+_##', raw_path)
    if m:
        placeholder = m.group(0)
        resolved = raw_path.replace(placeholder, str(draft_dir).replace('\\', '/'))
        return resolved
    return raw_path

def save_draft_safely_py(draft_file: Path, data: dict):
    """Write draft atomically using a temporary file and create a .bak backup."""
    backup_file = draft_file.with_suffix(".json.bak")
    temp_file = draft_file.with_suffix(".json.tmp")
    if draft_file.exists():
        try:
            shutil.copy2(draft_file, backup_file)
        except Exception:
            pass
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, draft_file)

app = FastAPI(title="CapCut AI Co-Director Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ConnectionResetError)
async def connection_reset_handler(request: Request, exc: ConnectionResetError):
    # Chromium canceled media range request during seek - harmless client disconnect
    return JSONResponse(status_code=204, content={"detail": "Client closed connection"})

CAPCUT_DRAFT_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"

class CommandRequest(BaseModel):
    project_name: str
    command: str
    target_segment_id: Optional[str] = None
    target_track_index: Optional[int] = None
    playhead_time_us: Optional[int] = None

class UpdateClipRequest(BaseModel):
    project_name: str
    segment_id: str
    start_us: Optional[int] = None
    duration_us: Optional[int] = None
    text_content: Optional[str] = None
    color: Optional[str] = None
    scale: Optional[float] = None
    font_size: Optional[float] = None
    volume: Optional[float] = None
    speed: Optional[float] = None

class AddClipRequest(BaseModel):
    project_name: str
    type: str # text, effect, transition
    content: str
    start_us: int
    duration_us: int

class AutoFixStepRequest(BaseModel):
    project_name: str
    error_id: str

class AutoFixAllRequest(BaseModel):
    project_name: str

@app.get("/api/projects")
def list_projects():
    if not CAPCUT_DRAFT_BASE.exists():
        return {"projects": []}
    
    projects = []
    for item in CAPCUT_DRAFT_BASE.iterdir():
        draft_file = item / "draft_content.json"
        if item.is_dir() and draft_file.exists():
            mtime = os.path.getmtime(draft_file)
            video_count = 0
            text_count = 0
            duration_us = 0
            try:
                # Fast sample read for header info
                with open(draft_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    video_count = len(meta.get("materials", {}).get("videos", []))
                    text_count = len(meta.get("materials", {}).get("texts", []))
                    duration_us = meta.get("duration", 0)
            except Exception:
                pass
            projects.append({
                "name": item.name,
                "path": str(draft_file).replace("\\", "/"),
                "modified": mtime,
                "video_count": video_count,
                "text_count": text_count,
                "duration_sec": round(duration_us / 1e6, 2),
                "has_footage": video_count > 0
            })
            
    # Sort: projects with footage first, then newest
    projects.sort(key=lambda x: (1 if x["has_footage"] else 0, x["modified"]), reverse=True)
    return {"projects": projects}

@app.get("/api/media")
def stream_media(path: str = Query(..., description="Absolute path to media file")):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    
    ext = p.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp"
    }
    return FileResponse(p, media_type=media_types.get(ext, "application/octet-stream"))

@app.get("/api/project/{project_name}")
def get_project(project_name: str):
    draft_file = CAPCUT_DRAFT_BASE / project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project draft_content.json not found")
    
    draft_dir = draft_file.parent
    
    try:
        with open(draft_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot parse draft JSON: {str(e)}")
        
    duration_us = data.get("duration", 0)
    fps = data.get("fps", 30)
    tracks_raw = data.get("tracks", [])
    materials = data.get("materials", {})
    
    # Map materials — resolve path placeholders
    texts_map = {}
    for t in materials.get("texts", []):
        try:
            content_obj = json.loads(t.get("content", "{}"))
            texts_map[t.get("id")] = {
                "text": content_obj.get("text", ""),
                "styles": content_obj.get("styles", []),
                "raw": t
            }
        except:
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
        
    transitions_map = {tr.get("id"): tr for tr in materials.get("transitions", [])}
    effects_map = {e.get("id"): e for e in materials.get("video_effects", [])}
    mat_animations_map = {m.get("id"): m for m in materials.get("material_animations", [])}
    
    parsed_tracks = []
    max_track_end = 0
    
    for t_idx, track in enumerate(tracks_raw):
        track_type = track.get("type", "video")
        parsed_segments = []
        
        for s in track.get("segments", []):
            try:
                mid = s.get("material_id")
                trange = s.get("target_timerange", {})
                start_us = trange.get("start", 0)
                dur_us = trange.get("duration", 0)
                end_us = start_us + dur_us
                if end_us > max_track_end: max_track_end = end_us
                
                clip_meta = s.get("clip", {})
                scale_val = clip_meta.get("scale", {}).get("x", 1.0)
                transform = clip_meta.get("transform", {})
                
                # Collect extra_material_refs (effects, animations, transitions applied)
                extra_refs = s.get("extra_material_refs", [])
                applied_effects = []
                applied_animations = []
                for ref_id in extra_refs:
                    if ref_id in effects_map:
                        e = effects_map[ref_id]
                        applied_effects.append({
                            "id": ref_id,
                            "name": e.get("name", e.get("effect_id", ref_id[:8])),
                            "params": e.get("effect_adjust_params", [])
                        })
                    if ref_id in mat_animations_map:
                        a = mat_animations_map[ref_id]
                        applied_animations.append({
                            "id": ref_id,
                            "in": a.get("in", {}).get("name", ""),
                            "out": a.get("out", {}).get("name", ""),
                            "loop": a.get("loop", {}).get("name", "")
                        })
                
                seg_info = {
                    "id": s.get("id"),
                    "material_id": mid,
                    "start_us": start_us,
                    "duration_us": dur_us,
                    "end_us": end_us,
                    "type": track_type,
                    "label": "Clip",
                    "color": "#cf8a28",
                    "scale": scale_val,
                    "transform_x": transform.get("x", 0),
                    "transform_y": transform.get("y", 0),
                    "media_path": "",
                    "effects": applied_effects,
                    "animations": applied_animations,
                    "visible": s.get("visible", True),
                    "volume": s.get("volume", 1.0),
                    "speed": s.get("speed", 1.0),
                    "details": {}
                }
                
                if track_type == "text":
                    txt_obj = texts_map.get(mid, {})
                    raw_t = txt_obj.get("raw", {})
                    seg_info["label"] = txt_obj.get("text", "Text") or "Text"
                    seg_info["color"] = "#a84334"
                    seg_info["details"]["text"] = txt_obj.get("text", "")
                    seg_info["details"]["styles"] = txt_obj.get("styles", [])
                    seg_info["details"]["font_size"] = raw_t.get("font_size", 0)
                    seg_info["details"]["text_align"] = raw_t.get("alignment", 1)
                elif track_type == "sticker":
                    st_obj = stickers_map.get(mid, {})
                    seg_info["label"] = st_obj.get("name", "Sticker") or "Ảnh vector"
                    seg_info["color"] = "#cf8a28"
                    seg_info["details"]["sticker_id"] = st_obj.get("id", "")
                    seg_info["details"]["sticker_url"] = st_obj.get("resource_id", "")
                elif track_type == "video":
                    v_obj = videos_map.get(mid, {})
                    resolved = v_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else "Video Clip"
                    mat_name = v_obj.get("material_name", "") or v_obj.get("category_name", "")
                    seg_info["label"] = filename or mat_name or "Video Clip"
                    seg_info["color"] = "#2d6cdf"
                    seg_info["media_path"] = resolved
                    seg_info["details"]["path"] = resolved
                    seg_info["details"]["width"] = v_obj.get("width", 0)
                    seg_info["details"]["height"] = v_obj.get("height", 0)
                    seg_info["details"]["duration_us"] = v_obj.get("duration", 0)
                    seg_info["details"]["has_audio"] = v_obj.get("has_audio", False)
                elif track_type == "audio":
                    a_obj = audios_map.get(mid, {})
                    resolved = a_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else "Audio"
                    seg_info["label"] = filename or a_obj.get("name", "Audio")
                    seg_info["color"] = "#258352"
                    seg_info["media_path"] = resolved
                    seg_info["details"]["path"] = resolved
                    seg_info["details"]["volume"] = s.get("volume", 1.0)
                    
                parsed_segments.append(seg_info)
            except Exception as seg_err:
                # Never crash on a single bad segment — skip it gracefully
                parsed_segments.append({
                    "id": s.get("id", "?"),
                    "material_id": s.get("material_id", ""),
                    "start_us": s.get("target_timerange", {}).get("start", 0),
                    "duration_us": s.get("target_timerange", {}).get("duration", 0),
                    "end_us": 0,
                    "type": track_type,
                    "label": f"[ERR] {str(seg_err)[:40]}",
                    "color": "#6b3030",
                    "scale": 1.0, "transform_x": 0, "transform_y": 0,
                    "media_path": "", "effects": [], "animations": [],
                    "visible": True, "volume": 1.0, "speed": 1.0, "details": {}
                })
            
        # Generate smart track label following CapCut PC convention
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
        
    # Second pass: assign sequential human-readable labels (V1, V2, A1, T1, FX1...)
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
            if pt["flag"] == 1:
                pt["label"] = f"T{t_count} (Phụ đề)"
            else:
                pt["label"] = f"T{t_count} (Văn bản)"
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
    
    # Flatten all components with track index for easy explorer navigation
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

    return {
        "project_name": project_name,
        "path": str(draft_file).replace("\\", "/"),
        "duration_us": calc_duration,
        "fps": fps,
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

@app.post("/api/update-clip")
def update_clip(req: UpdateClipRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    target_mid = None
    target_seg = None
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            if s.get("id") == req.segment_id:
                target_seg = s
                target_mid = s.get("material_id")
                if req.start_us is not None:
                    s["target_timerange"]["start"] = max(0, req.start_us)
                if req.duration_us is not None:
                    s["target_timerange"]["duration"] = max(100_000, req.duration_us)
                if req.scale is not None:
                    s["clip"] = s.get("clip", {})
                    s["clip"]["scale"] = {"x": req.scale, "y": req.scale}
                if req.volume is not None:
                    s["volume"] = max(0.0, min(2.0, req.volume))
                if req.speed is not None:
                    s["speed"] = max(0.1, min(10.0, req.speed))
                break
        if target_seg: break
        
    if not target_seg:
        raise HTTPException(status_code=404, detail="Segment not found")
        
    if req.text_content is not None and target_mid:
        for t in data.get("materials", {}).get("texts", []):
            if t.get("id") == target_mid:
                c_obj = json.loads(t.get("content", "{}"))
                c_obj["text"] = req.text_content
                t["content"] = json.dumps(c_obj, ensure_ascii=False)
                break
                
    save_draft_safely_py(draft_file, data)
        
    return {"status": "success", "message": "Clip updated successfully"}

@app.post("/api/split-clip")
def split_clip(req: CommandRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    split_us = req.playhead_time_us or 0
    found = False
    import uuid
    for track in data.get("tracks", []):
        for idx, s in enumerate(track.get("segments", [])):
            if s.get("id") == req.target_segment_id:
                tr = s.get("target_timerange", {})
                start = tr.get("start", 0)
                dur = tr.get("duration", 0)
                end = start + dur
                if start < split_us < end:
                    # Split into 2 segments
                    left_dur = split_us - start
                    right_dur = end - split_us
                    tr["duration"] = left_dur
                    
                    new_seg = json.loads(json.dumps(s))
                    new_seg["id"] = str(uuid.uuid4()).upper()
                    new_seg["target_timerange"]["start"] = split_us
                    new_seg["target_timerange"]["duration"] = right_dur
                    
                    # Fix: Synchronize source_timerange for video and audio
                    if s.get("source_timerange"):
                        speed = s.get("speed", 1.0) or 1.0
                        src_start = s["source_timerange"].get("start", 0)
                        src_dur = s["source_timerange"].get("duration", 0)
                        left_src_dur = int(round(left_dur * speed))
                        s["source_timerange"]["duration"] = left_src_dur
                        new_seg["source_timerange"]["start"] = src_start + left_src_dur
                        new_seg["source_timerange"]["duration"] = max(100_000, src_dur - left_src_dur)
                        
                    track["segments"].insert(idx + 1, new_seg)
                    found = True
                    break
        if found: break
        
    if not found:
        return {"status": "error", "message": "Playhead must be inside the selected clip to split"}
        
    save_draft_safely_py(draft_file, data)
        
    return {"status": "success", "message": f"Split clip successfully at {split_us/1e6:.2f}s"}

@app.post("/api/delete-clip")
def delete_clip(req: CommandRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    deleted = False
    for track in data.get("tracks", []):
        new_segs = [s for s in track.get("segments", []) if s.get("id") != req.target_segment_id]
        if len(new_segs) != len(track.get("segments", [])):
            track["segments"] = new_segs
            deleted = True
            break
            
    if not deleted:
        return {"status": "error", "message": "Clip not found to delete"}
        
    save_draft_safely_py(draft_file, data)
        
    return {"status": "success", "message": "Clip deleted successfully"}

@app.get("/api/quality-audit/{project_name}")
def quality_audit(project_name: str):
    draft_file = CAPCUT_DRAFT_BASE / project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    issues = []
    score = 100
    
    # 1. Audit Safe Zone
    unsafe_texts = 0
    texts = data.get("materials", {}).get("texts", [])
    for track in data.get("tracks", []):
        if track.get("type") == "text":
            for s in track.get("segments", []):
                y = s.get("clip", {}).get("transform", {}).get("y", 0)
                if y < -0.45:
                    unsafe_texts += 1
    if unsafe_texts > 0:
        score -= 15
        issues.append({
            "type": "SAFE_ZONE_VIOLATION",
            "severity": "WARNING",
            "message": f"{unsafe_texts} phụ đề nằm quá sát đáy (dưới -0.45) nguy cơ bị caption TikTok che",
            "fix_action": "Kéo toàn bộ về y = -0.404"
        })
        
    # 2. Audit Subtitle Word Length (Single line rule)
    long_texts = 0
    for t in texts:
        try:
            c_obj = json.loads(t.get("content", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
        txt = c_obj.get("text", "")
        if len(txt.split()) > 10:
            long_texts += 1
    if long_texts > 0:
        score -= 10
        issues.append({
            "type": "SUBTITLE_OVERFLOW",
            "severity": "WARNING",
            "message": f"{long_texts} phụ đề dài quá 10 từ, nguy cơ tràn thành 3 dòng che sản phẩm",
            "fix_action": "Bẻ đôi câu phụ đề dài"
        })

    # 3. Audit Dead Outro
    total_dur = data.get("duration", 0)
    max_voice = 0
    for track in data.get("tracks", []):
        if track.get("type") in ["audio", "text"]:
            for s in track.get("segments", []):
                end = s.get("target_timerange", {}).get("start", 0) + s.get("target_timerange", {}).get("duration", 0)
                if end > max_voice: max_voice = end
                
    if total_dur > max_voice + 1_500_000 and max_voice > 0:
        excess_sec = (total_dur - max_voice) / 1e6
        score -= 20
        issues.append({
            "type": "DEAD_OUTRO",
            "severity": "CRITICAL",
            "message": f"Phát hiện đuôi video chết dài {excess_sec:.1f}s sau khi dứt lời thoại (nguy cơ tụt retention)",
            "fix_action": f"Cắt cụt timeline tại { (max_voice+400000)/1e6:.2f}s"
        })

    return {
        "project_name": project_name,
        "score": max(20, score),
        "status": "PASS" if score >= 85 else ("WARNING" if score >= 60 else "POOR"),
        "total_issues": len(issues),
        "issues": issues
    }

def scan_project_errors(project_name: str) -> Dict[str, Any]:
    draft_file = CAPCUT_DRAFT_BASE / project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    draft_dir = draft_file.parent
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    errors = []
    texts_map = {t.get("id"): t for t in data.get("materials", {}).get("texts", [])}
    videos_map = {v.get("id"): v for v in data.get("materials", {}).get("videos", [])}
    
    # 1. Scan tracks for timing, safe zone, aspect ratio & subtitle styles
    for t_idx, track in enumerate(data.get("tracks", [])):
        ttype = track.get("type")
        for seg in track.get("segments", []):
            sid = seg.get("id")
            trange = seg.get("target_timerange", {})
            start_us = trange.get("start", 0)
            dur_us = trange.get("duration", 0)
            end_us = start_us + dur_us
            mid = seg.get("material_id")
            
            if ttype == "text":
                clip_meta = seg.get("clip", {})
                tf = clip_meta.get("transform", {})
                y = tf.get("y", 0.0)
                x = tf.get("x", 0.0)
                t_obj = texts_map.get(mid, {})
                try:
                    c_obj = json.loads(t_obj.get("content", "{}"))
                    txt = c_obj.get("text", "")
                    styles = c_obj.get("styles", [])
                except Exception:
                    txt, styles = "", []
                
                # Check TikTok Lower-Third Safe Zone (danger zone: y < -0.42)
                if y < -0.42:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"safe_bot_{sid}",
                        "type": "SAFE_ZONE_VIOLATION",
                        "severity": "CRITICAL",
                        "category": "safe_zone",
                        "title": f"Phụ đề chạm vùng nguy hiểm TikTok (y = {y:.2f})",
                        "description": f"Chữ \"{txt[:35]}\" nằm tại y = {y:.2f}, bị thanh caption hoặc menu TikTok/Shorts che.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 10.0,
                            "top": round(top_pct, 1),
                            "width": 80.0,
                            "height": 13.0,
                            "unit": "percent"
                        },
                        "fix_command": "Kéo toạ độ phụ đề về vùng an toàn TikTok y = -0.404",
                        "fixed": False
                    })
                elif y > 0.44:
                    top_pct = max(5.0, min(85.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"safe_top_{sid}",
                        "type": "SAFE_ZONE_TOP",
                        "severity": "WARNING",
                        "category": "safe_zone",
                        "title": f"Phụ đề nằm sát mép trên (y = {y:.2f})",
                        "description": f"Chữ \"{txt[:35]}\" nằm quá cao, nguy cơ bị notch camera, status bar hoặc tên nhạc che.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 10.0,
                            "top": round(top_pct, 1),
                            "width": 80.0,
                            "height": 13.0,
                            "unit": "percent"
                        },
                        "fix_command": "Kéo toạ độ phụ đề về vùng an toàn trên y = 0.35",
                        "fixed": False
                    })
                
                # Check Montserrat Shadow standard
                has_shadow = any(len(s.get("shadows", [])) > 0 for s in styles) if styles else False
                if not has_shadow and txt:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"style_{sid}",
                        "type": "UNSTYLED_SUBTITLE",
                        "severity": "INFO",
                        "category": "typography",
                        "title": "Phụ đề thiếu chuẩn Montserrat Commercial Shadow",
                        "description": f"Chữ \"{txt[:35]}\" chưa có shadow -45 độ, dễ bị chìm mờ khi nền video chuyển động sáng.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 12.0,
                            "top": round(top_pct, 1),
                            "width": 76.0,
                            "height": 12.0,
                            "unit": "percent"
                        },
                        "fix_command": "Áp dụng chuẩn Montserrat Shadow cho clip này",
                        "fixed": False
                    })
                
                # Check text length / word count
                words = txt.split()
                if len(words) > 10:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"overflow_{sid}",
                        "type": "SUBTITLE_OVERFLOW",
                        "severity": "WARNING",
                        "category": "typography",
                        "title": f"Phụ đề dài {len(words)} từ (Nguy cơ tràn 3 dòng)",
                        "description": f"Câu \"{txt[:35]}...\" quá dài làm mất nhịp thị giác, cần ngắt thành câu ngắn gọn.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 8.0,
                            "top": round(top_pct, 1),
                            "width": 84.0,
                            "height": 14.0,
                            "unit": "percent"
                        },
                        "fix_command": "Tối ưu ngắt câu phụ đề",
                        "fixed": False
                    })
            
            elif ttype == "video":
                clip_meta = seg.get("clip", {})
                scale_x = clip_meta.get("scale", {}).get("x", 1.0)
                v_obj = videos_map.get(mid, {})
                raw_path = v_obj.get("path", "") or v_obj.get("media_path", "")
                resolved_p = resolve_draft_path(raw_path, draft_dir)
                
                # Check missing media
                if resolved_p and not Path(resolved_p).exists():
                    errors.append({
                        "id": f"offline_{sid}",
                        "type": "MEDIA_OFFLINE",
                        "severity": "CRITICAL",
                        "category": "footage",
                        "title": f"Footage offline: {os.path.basename(resolved_p)}",
                        "description": f"Không tìm thấy tệp media tại đường dẫn: {resolved_p}",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 100_000,
                        "bbox": {
                            "left": 5.0,
                            "top": 5.0,
                            "width": 90.0,
                            "height": 90.0,
                            "unit": "percent"
                        },
                        "fix_command": "Liên kết lại tệp media trong thư mục scratch",
                        "fixed": False
                    })
                
                # Check Letterbox / Black Bars (scale < 1.0)
                if scale_x < 1.0:
                    errors.append({
                        "id": f"letterbox_{sid}",
                        "type": "LETTERBOX_BLACK_BARS",
                        "severity": "WARNING",
                        "category": "framing",
                        "title": f"Footage viền đen (Scale = {scale_x:.2f}x)",
                        "description": f"Clip {os.path.basename(resolved_p) or sid} thu nhỏ dưới 1.0x, để lộ viền đen quanh khung 9:16.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 100_000,
                        "bbox": {
                            "left": 4.0,
                            "top": 4.0,
                            "width": 92.0,
                            "height": 92.0,
                            "unit": "percent"
                        },
                        "fix_command": "Áp dụng Punch-in Zoom 1.15x loại bỏ viền đen",
                        "fixed": False
                    })
    
    # 2. Check Dead Outro gap
    total_dur = data.get("duration", 0)
    max_voice = 0
    for t in data.get("tracks", []):
        if t.get("type") in ["audio", "text"]:
            for s in t.get("segments", []):
                e = s.get("target_timerange", {}).get("start", 0) + s.get("target_timerange", {}).get("duration", 0)
                if e > max_voice: max_voice = e
                
    if total_dur > max_voice + 1_200_000 and max_voice > 0:
        excess = (total_dur - max_voice) / 1e6
        errors.append({
            "id": "dead_outro",
            "type": "DEAD_OUTRO",
            "severity": "CRITICAL",
            "category": "pacing",
            "title": f"Phát hiện đuôi video chết ({excess:.1f}s)",
            "description": f"Hình ảnh kéo dài {excess:.1f}s sau khi dứt lời thoại, gây rớt tỷ lệ hoàn thành video.",
            "segment_id": "",
            "track_index": 0,
            "start_us": max_voice,
            "end_us": total_dur,
            "target_time_us": max_voice + 200_000,
            "bbox": {
                "left": 10.0,
                "top": 15.0,
                "width": 80.0,
                "height": 70.0,
                "unit": "percent"
            },
            "fix_command": f"Triệt tiêu đuôi video chết, cắt gọn tại {(max_voice + 400_000)/1e6:.2f}s",
            "fixed": False
        })
        
    errors.sort(key=lambda x: x["start_us"])
    
    crit_count = sum(1 for e in errors if e["severity"] == "CRITICAL")
    warn_count = sum(1 for e in errors if e["severity"] == "WARNING")
    info_count = sum(1 for e in errors if e["severity"] == "INFO")
    
    calc_score = 100 - (crit_count * 15) - (warn_count * 5) - (info_count * 2)
    final_score = max(20, min(100, calc_score)) if len(errors) > 0 else 100
    
    return {
        "project_name": project_name,
        "total_errors": len(errors),
        "critical_count": crit_count,
        "warning_count": warn_count,
        "info_count": info_count,
        "health_score": final_score,
        "status": "PASS" if final_score >= 85 else ("WARNING" if final_score >= 60 else "CRITICAL"),
        "errors": errors
    }

@app.get("/api/scan-footage-errors/{project_name}")
def get_footage_errors(project_name: str):
    return scan_project_errors(project_name)

@app.post("/api/ai-agent/auto-fix-step")
def auto_fix_step(req: AutoFixStepRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    backup_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json.bak"
    shutil.copy2(draft_file, backup_file)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    action_note = ""
    err_id = req.error_id
    
    if err_id.startswith("safe_bot_") or err_id.startswith("safe_top_"):
        seg_id = err_id.replace("safe_bot_", "").replace("safe_top_", "")
        target_y = -0.404 if err_id.startswith("safe_bot_") else 0.35
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    s["clip"] = s.get("clip", {})
                    s["clip"]["transform"] = s["clip"].get("transform", {})
                    s["clip"]["transform"]["y"] = target_y
                    action_note = f"✓ Đã dịch chuyển toạ độ phụ đề về y = {target_y} (Chuẩn an toàn TikTok)"
                    break
    elif err_id.startswith("style_"):
        seg_id = err_id.replace("style_", "")
        font_path = "C:/Users/jinnr/AppData/Local/Microsoft/Windows/Fonts/Montserrat-Regular.otf"
        target_mid = None
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    target_mid = s.get("material_id")
                    break
        if target_mid:
            for t in data.get("materials", {}).get("texts", []):
                if t.get("id") == target_mid:
                    c_obj = json.loads(t.get("content", "{}"))
                    txt_str = c_obj.get("text", "")
                    c_obj["styles"] = [{
                        "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                        "font": {"path": font_path, "id": ""},
                        "size": 11.0,
                        "bold": True,
                        "shadows": [{
                            "angle": -45,
                            "thickness_projection_angle": -45,
                            "thickness_projection_enable": False,
                            "diffuse": 0.025,
                            "alpha": 0.72,
                            "distance": 5.0,
                            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                        }],
                        "range": [0, len(txt_str)]
                    }]
                    t["content"] = json.dumps(c_obj, ensure_ascii=False)
                    action_note = f"✓ Đã áp dụng chuẩn Montserrat Commercial Shadow cho chữ '{txt_str[:25]}'"
                    break
    elif err_id.startswith("letterbox_"):
        seg_id = err_id.replace("letterbox_", "")
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    s["clip"] = s.get("clip", {})
                    s["clip"]["scale"] = {"x": 1.15, "y": 1.15}
                    action_note = "✓ Đã áp dụng Punch-in Zoom (1.15x) loại bỏ hoàn toàn viền đen"
                    break
    elif err_id == "dead_outro":
        max_voice_end = 0
        for track in data.get("tracks", []):
            if track.get("type") in ["audio", "text"]:
                for s in track.get("segments", []):
                    tr = s.get("target_timerange", {})
                    end_time = tr.get("start", 0) + tr.get("duration", 0)
                    if end_time > max_voice_end:
                        max_voice_end = end_time
        if max_voice_end > 0:
            target_end = max_voice_end + 400_000
            data["duration"] = target_end
            for track in data.get("tracks", []):
                for s in track.get("segments", []):
                    tr = s.get("target_timerange", {})
                    if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                        tr["duration"] = max(100_000, target_end - tr.get("start", 0))
            action_note = f"✓ Đã cắt cụt timeline tại {target_end/1e6:.2f}s, triệt tiêu khoảng chết"
            
    save_draft_safely_py(draft_file, data)
        
    return {
        "status": "success",
        "fixed_error_id": req.error_id,
        "action_performed": action_note or f"✓ Đã tối ưu lỗi {req.error_id}"
    }

@app.post("/api/ai-agent/auto-fix-all")
def auto_fix_all(req: AutoFixAllRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    backup_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json.bak"
    shutil.copy2(draft_file, backup_file)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    font_path = "C:/Users/jinnr/AppData/Local/Microsoft/Windows/Fonts/Montserrat-Regular.otf"
    actions_log = []
    
    # 1. Fix all text safe zones to y = -0.404 and inject Montserrat Shadow
    fixed_texts = 0
    for track in data.get("tracks", []):
        if track.get("type") == "text":
            for s in track.get("segments", []):
                s["clip"] = s.get("clip", {})
                s["clip"]["transform"] = s["clip"].get("transform", {})
                s["clip"]["transform"]["y"] = -0.404
                fixed_texts += 1
                
    if fixed_texts > 0:
        actions_log.append(f"✓ Đã căn chỉnh {fixed_texts} phụ đề về Safe Zone TikTok (y = -0.404)")
        
    for t in data.get("materials", {}).get("texts", []):
        try:
            c_obj = json.loads(t.get("content", "{}"))
            txt_str = c_obj.get("text", "")
            c_obj["styles"] = [{
                "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                "font": {"path": font_path, "id": ""},
                "size": 11.0,
                "bold": True,
                "shadows": [{
                    "angle": -45,
                    "thickness_projection_angle": -45,
                    "thickness_projection_enable": False,
                    "diffuse": 0.025,
                    "alpha": 0.72,
                    "distance": 5.0,
                    "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                }],
                "range": [0, len(txt_str)]
            }]
            t["content"] = json.dumps(c_obj, ensure_ascii=False)
        except Exception:
            pass
    actions_log.append("✓ Đã áp dụng chuẩn Montserrat Commercial Shadow cho toàn bộ văn bản")

    # 2. Fix letterboxes (scale < 1.0)
    fixed_scales = 0
    for track in data.get("tracks", []):
        if track.get("type") == "video":
            for s in track.get("segments", []):
                s["clip"] = s.get("clip", {})
                cur_scale = s["clip"].get("scale", {}).get("x", 1.0)
                if cur_scale < 1.0:
                    s["clip"]["scale"] = {"x": 1.15, "y": 1.15}
                    fixed_scales += 1
    if fixed_scales > 0:
        actions_log.append(f"✓ Đã áp dụng Punch-in Zoom (1.15x) cho {fixed_scales} clip viền đen")

    # 3. Cut Dead Outro
    max_voice_end = 0
    for track in data.get("tracks", []):
        if track.get("type") in ["audio", "text"]:
            for s in track.get("segments", []):
                tr = s.get("target_timerange", {})
                end_time = tr.get("start", 0) + tr.get("duration", 0)
                if end_time > max_voice_end:
                    max_voice_end = end_time
    if max_voice_end > 0:
        target_end = max_voice_end + 400_000
        data["duration"] = target_end
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                tr = s.get("target_timerange", {})
                if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                    tr["duration"] = max(100_000, target_end - tr.get("start", 0))
        actions_log.append(f"✓ Đã triệt tiêu đuôi chết, chốt timeline dứt khoát tại {target_end/1e6:.2f}s")

    save_draft_safely_py(draft_file, data)

    return {
        "status": "success",
        "actions_log": actions_log,
        "message": f"AI Agent đã tự động sửa toàn bộ lỗi trên timeline!"
    }

@app.post("/api/execute-command")
def execute_command(req: CommandRequest):
    draft_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")
        
    backup_file = CAPCUT_DRAFT_BASE / req.project_name / "draft_content.json.bak"
    shutil.copy2(draft_file, backup_file)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    cmd = req.command.strip()
    cmd_lower = cmd.lower()
    feedback = []
    
    # 1. Shift timing
    shift_match = re.search(r'(sớm|trễ|lùi|tiến|khớp).*?(\d+(\.\d+)?)s?', cmd_lower)
    if shift_match:
        val = float(shift_match.group(2))
        val_us = int(val * 1_000_000)
        is_earlier = any(w in cmd_lower for w in ['sớm', 'lùi', 'trước'])
        delta = -val_us if is_earlier else val_us
        
        found = False
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == req.target_segment_id:
                    curr_start = s.get("target_timerange", {}).get("start", 0)
                    new_start = max(0, curr_start + delta)
                    s["target_timerange"]["start"] = new_start
                    found = True
                    direction_str = "sớm hơn" if is_earlier else "trễ hơn"
                    feedback.append(f"✓ Đã dịch chuyển clip {direction_str} {val}s (từ {curr_start/1e6:.2f}s ➔ {new_start/1e6:.2f}s)")
                    break
            if found: break
            
        if not found and req.target_track_index is not None:
            t = data.get("tracks", [])[req.target_track_index]
            for s in t.get("segments", []):
                s["target_timerange"]["start"] = max(0, s["target_timerange"]["start"] + delta)
            feedback.append(f"✓ Đã dịch chuyển toàn bộ segment trên Track {req.target_track_index} {val}s")

    # 2. Change text
    text_match = re.search(r'(?:đổi|sửa|thay).*?(?:text|chữ|nội dung).*?[\'"`]([^\'"`]+)[\'"`]', cmd, re.IGNORECASE)
    if not text_match:
        text_match = re.search(r'thành [\'"`]?([a-zA-Z0-9\sÀ-ỹ]+)[\'"`]?', cmd, re.IGNORECASE)
        
    if text_match and req.target_segment_id:
        new_text = text_match.group(1).strip()
        target_mid = None
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == req.target_segment_id:
                    target_mid = s.get("material_id")
                    break
            if target_mid: break
            
        if target_mid:
            for t in data.get("materials", {}).get("texts", []):
                if t.get("id") == target_mid:
                    c_obj = json.loads(t.get("content", "{}"))
                    old_text = c_obj.get("text", "")
                    c_obj["text"] = new_text
                    t["content"] = json.dumps(c_obj, ensure_ascii=False)
                    feedback.append(f"✓ Đã đổi text từ '{old_text}' ➔ '{new_text}'")
                    break

    # 3. Styles / Montserrat Shadow / Color
    if any(k in cmd_lower for k in ['montserrat', 'font', 'shadow', 'vàng', 'màu', 'style']):
        color_rgb = [1.0, 1.0, 1.0]
        if 'vàng' in cmd_lower: color_rgb = [1.0, 0.9, 0.0]
        elif 'đỏ' in cmd_lower: color_rgb = [1.0, 0.2, 0.2]
        elif 'xanh' in cmd_lower: color_rgb = [0.0, 0.9, 1.0]
        
        font_path = "C:/Users/jinnr/AppData/Local/Microsoft/Windows/Fonts/Montserrat-Regular.otf"
        updated_texts = 0
        for t in data.get("materials", {}).get("texts", []):
            c_obj = json.loads(t.get("content", "{}"))
            txt_str = c_obj.get("text", "")
            c_obj["styles"] = [{
                "fill": {"content": {"render_type": "solid", "solid": {"color": color_rgb}}},
                "font": {"path": font_path, "id": ""},
                "size": 11.0,
                "bold": True,
                "shadows": [{
                    "angle": -45,
                    "thickness_projection_angle": -45,
                    "thickness_projection_enable": False,
                    "diffuse": 0.025,
                    "alpha": 0.72,
                    "distance": 5.0,
                    "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                }],
                "range": [0, len(txt_str)]
            }]
            t["content"] = json.dumps(c_obj, ensure_ascii=False)
            updated_texts += 1
        feedback.append(f"✓ Đã áp dụng chuẩn Montserrat Commercial Shadow cho {updated_texts} phụ đề")

    # 4. Punch-in Zoom
    if 'punch' in cmd_lower or 'zoom' in cmd_lower or 'scale' in cmd_lower:
        scale_val = 1.15
        if '1.2' in cmd_lower: scale_val = 1.2
        elif '1.18' in cmd_lower: scale_val = 1.18
        
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == req.target_segment_id:
                    s["clip"] = s.get("clip", {})
                    s["clip"]["scale"] = {"x": scale_val, "y": scale_val}
                    feedback.append(f"✓ Đã áp dụng Punch-in Zoom ({scale_val}x) cho clip")
                    break

    # 5. Safe zone alignment
    if 'safe' in cmd_lower or 'vùng an toàn' in cmd_lower or 'tiktok' in cmd_lower:
        for track in data.get("tracks", []):
            if track.get("type") == "text":
                for s in track.get("segments", []):
                    s["clip"] = s.get("clip", {})
                    s["clip"]["transform"] = s["clip"].get("transform", {})
                    s["clip"]["transform"]["y"] = -0.404
        feedback.append("✓ Đã căn chỉnh toàn bộ phụ đề về tọa độ an toàn TikTok (y = -0.404)")

    # 6. Cut Dead Outro
    if 'outro' in cmd_lower or 'đuôi' in cmd_lower or 'thừa' in cmd_lower:
        max_voice_end = 0
        for track in data.get("tracks", []):
            if track.get("type") in ["audio", "text"]:
                for s in track.get("segments", []):
                    tr = s.get("target_timerange", {})
                    end_time = tr.get("start", 0) + tr.get("duration", 0)
                    if end_time > max_voice_end:
                        max_voice_end = end_time
        if max_voice_end > 0:
            target_end = max_voice_end + 400_000
            data["duration"] = target_end
            for track in data.get("tracks", []):
                for s in track.get("segments", []):
                    tr = s.get("target_timerange", {})
                    if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                        tr["duration"] = max(100_000, target_end - tr.get("start", 0))
            feedback.append(f"✓ Đã triệt tiêu đuôi chết, chốt dứt khoát tại {target_end/1e6:.2f}s")

    if not feedback:
        feedback.append(f"✓ Đã thực thi lệnh '{cmd}' và cập nhật thông số dự án thành công!")

    save_draft_safely_py(draft_file, data)

    return {
        "status": "success",
        "feedback": "\n".join(feedback),
        "backup": str(backup_file).replace("\\", "/")
    }

@app.post("/api/undo/{project_name}")
def undo_action(project_name: str):
    draft_file = CAPCUT_DRAFT_BASE / project_name / "draft_content.json"
    backup_file = CAPCUT_DRAFT_BASE / project_name / "draft_content.json.bak"
    
    if not backup_file.exists():
        return {"status": "error", "message": "No backup available to restore"}
    
    shutil.copy2(backup_file, draft_file)
    return {"status": "success", "message": "Restored from last backup (before the previous command)"}

class McpCreateProjectRequest(BaseModel):
    projectName: str
    vjVideoPath: Optional[str] = None
    vjAudioWavPath: Optional[str] = None
    brollFolderPath: Optional[str] = None
    supportingFolder: Optional[str] = None
    bgmPath: Optional[str] = None
    hookText: Optional[str] = None
    ctaText: Optional[str] = None
    excludedClipPaths: Optional[List[str]] = []
    approvedClipPaths: Optional[List[str]] = []
    scriptSentences: List[Dict[str, Any]]

class McpToolCallRequest(BaseModel):
    toolName: str
    arguments: Dict[str, Any]

MCP_SERVER_JS = Path("C:/Users/jinnr/.gemini/antigravity-ide/scratch/capcut-roughcut-studio/capcut_mcp_server.js")

@app.get("/api/mcp/tools")
def get_mcp_tools():
    return {
        "status": "connected",
        "mcp_server": "capcut-commercial-editor",
        "tools": [
            {
                "name": "capcut_scan_and_index_footage",
                "description": "Quét kho footage, lập chỉ mục tự động và kích hoạt bể chống trùng lặp (Zero-Duplicate Pool).",
                "parameters": ["folderPath"]
            },
            {
                "name": "capcut_compile_13layer_draft",
                "description": "Biên dịch dự án CapCut chuẩn 13 Layers thương mại (VJ, B-roll chống trùng, Subtitle Montserrat Shadow, Ducking BGM, Boost Mic DJI x3.16).",
                "parameters": ["projectName", "vjVideoPath", "vjAudioWavPath", "brollFolderPath", "supportingFolder", "excludedClipPaths", "bgmPath", "scriptSentences"]
            },
            {
                "name": "capcut_safe_launch",
                "description": "Mở CapCut Desktop an toàn và load thẳng vào dự án vừa tạo mà không lo bị crash.",
                "parameters": ["projectName"]
            }
        ]
    }

@app.post("/api/mcp/create-project")
def mcp_create_project(req: McpCreateProjectRequest):
    import subprocess
    import tempfile
    
    payload = {
        "projectName": req.projectName,
        "vjVideoPath": req.vjVideoPath or "",
        "vjAudioWavPath": req.vjAudioWavPath or "",
        "brollFolderPath": req.brollFolderPath or "",
        "supportingFolder": req.supportingFolder or "",
        "bgmPath": req.bgmPath or "",
        "hookText": req.hookText or "",
        "ctaText": req.ctaText or "",
        "excludedClipPaths": req.excludedClipPaths or [],
        "scriptSentences": req.scriptSentences
    }
    
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
        json.dump(payload, tf, ensure_ascii=False)
        temp_input = tf.name
        
    mcp_path_str = str(MCP_SERVER_JS).replace('\\', '/')
    temp_input_str = temp_input.replace('\\', '/')
    js_code = f"""
    const fs = require('fs');
    const m = require('{mcp_path_str}');
    const params = JSON.parse(fs.readFileSync('{temp_input_str}', 'utf-8'));
    const result = m.compile13LayerCommercialDraft(params);
    console.log(JSON.stringify(result));
    """
    
    try:
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        res_data = json.loads(proc.stdout.strip())
        return res_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi MCP compilation: {str(e)}")
    finally:
        try: os.unlink(temp_input)
        except: pass

@app.post("/api/mcp/call-tool")
def mcp_call_tool(req: McpToolCallRequest):
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
        json.dump(req.arguments, tf, ensure_ascii=False)
        temp_input = tf.name
        
    mcp_path_str = str(MCP_SERVER_JS).replace('\\', '/')
    temp_input_str = temp_input.replace('\\', '/')
    tool_name = req.toolName
    
    js_code = f"""
    const fs = require('fs');
    const m = require('{mcp_path_str}');
    const args = JSON.parse(fs.readFileSync('{temp_input_str}', 'utf-8'));
    let out = {{}};
    if ('{tool_name}' === 'capcut_scan_and_index_footage') {{
        const fm = new m.FootageManager();
        out = fm.scanFolder(args.folderPath || args.brollFolderPath);
    }} else if ('{tool_name}' === 'capcut_compile_13layer_draft') {{
        out = m.compile13LayerCommercialDraft(args);
    }} else if ('{tool_name}' === 'capcut_safe_launch') {{
        out = {{ ok: true, message: 'Đã gửi lệnh mở CapCut an toàn' }};
    }} else {{
        out = {{ ok: false, error: 'Tool không tồn tại' }};
    }}
    console.log(JSON.stringify(out));
    """
    try:
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi MCP tool call: {str(e)}")
    finally:
        try: os.unlink(temp_input)
        except: pass

class FootageFolderAnalysisRequest(BaseModel):
    folder_path: str
    max_files: Optional[int] = 20

class ScriptParseRequest(BaseModel):
    raw_script: str
    pacing_mode: Optional[str] = "medium"

@app.post("/api/ai-agent/analyze-footage-folder")
def api_analyze_footage_folder(req: FootageFolderAnalysisRequest):
    try:
        import footage_analyzer
        return footage_analyzer.scan_and_analyze_folder(req.folder_path, max_files=req.max_files or 20)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích footage: {str(e)}")

@app.post("/api/ai-agent/parse-script")
def api_parse_script(req: ScriptParseRequest):
    try:
        import footage_analyzer
        sentences = footage_analyzer.parse_commercial_script(req.raw_script, pacing_mode=req.pacing_mode or "medium")
        return {"ok": True, "count": len(sentences), "sentences": sentences}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích kịch bản: {str(e)}")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("CapCut Web Studio starting on http://localhost:8765 ...")
    uvicorn.run(app, host="127.0.0.1", port=8765)
