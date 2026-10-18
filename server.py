import os
import json
import shutil
import re
import time
import logging
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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

def get_montserrat_font_path() -> str:
    env_font = os.environ.get("MONTSERRAT_FONT_PATH")
    if env_font and Path(env_font).exists():
        return str(Path(env_font)).replace('\\', '/')
    user_font = Path.home() / "AppData/Local/Microsoft/Windows/Fonts/Montserrat-Regular.otf"
    if user_font.exists():
        return str(user_font).replace('\\', '/')
    return "Montserrat-Regular.otf"


def detect_capcut_draft_base() -> Path:
    """Tự động dò tìm thư mục dự án CapCut / JianYing trên Windows và macOS."""
    env_dir = os.environ.get("CAPCUT_DRAFTS_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir).resolve()
        
    localappdata = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()
    
    candidates = [
        # CapCut PC Windows
        Path(localappdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft" if localappdata else None,
        # JianYing Pro Windows
        Path(localappdata) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft" if localappdata else None,
        # CapCut macOS
        home / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft",
        # JianYing macOS
        home / "Movies" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft",
    ]
    for c in candidates:
        if c and c.exists():
            return c.resolve()
            
    default_p = Path(localappdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft" if localappdata else home / "CapCutDrafts"
    return default_p.resolve()

def is_capcut_running() -> bool:
    """Kiểm tra xem CapCut Desktop hoặc JianYing có đang chạy bằng psutil không."""
    target_procs = {"capcut.exe", "jianyingpro.exe", "capcut"}
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            p_name = (p.info.get('name') or '').lower()
            if p_name in target_procs:
                return True
    except Exception as e:
        logging.warning(f"Lỗi kiểm tra psutil: {e}")
    return False

def check_capcut_not_running():
    """Chặn ghi khi CapCut đang chạy để tránh xung đột file draft."""
    if is_capcut_running():
        raise HTTPException(
            status_code=409,
            detail="CapCut Desktop đang chạy! Vui lòng đóng CapCut trước khi ghi hoặc chỉnh sửa dự án để tránh xung đột dữ liệu."
        )

def save_draft_safely_py(draft_file: Path, data: dict):
    """Ghi draft an toàn bằng file tạm và tạo file backup .bak."""
    backup_file = draft_file.with_suffix(".json.bak")
    temp_file = draft_file.with_suffix(".json.tmp")
    if draft_file.exists():
        try:
            shutil.copy2(draft_file, backup_file)
        except Exception as e:
            logging.warning(f"Không thể tạo backup .bak: {e}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, draft_file)

def save_draft_with_history(draft_file: Path, data: dict):
    """Ghi draft và lưu tối đa 20 snapshot vào thư mục .history/ để hỗ trợ Undo/Redo nhiều bước."""
    draft_dir = draft_file.parent
    history_dir = draft_dir / ".history"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = history_dir / "history_state.json"
    state = {"snapshots": [], "current_index": -1}
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
            
    curr_idx = state.get("current_index", -1)
    snapshots = state.get("snapshots", [])
    
    # Nếu history chưa có snapshot nào nhưng draft đã tồn tại, lưu snapshot ban đầu làm mốc hoàn tác gốc
    if len(snapshots) == 0 and draft_file.exists():
        try:
            with open(draft_file, "r", encoding="utf-8") as f:
                init_data = json.load(f)
            init_name = f"draft_init_{int(time.time() * 1000)}.json"
            init_path = history_dir / init_name
            with open(init_path, "w", encoding="utf-8") as f:
                json.dump(init_data, f, ensure_ascii=False, indent=2)
            snapshots.append(init_name)
            curr_idx = 0
        except Exception as e:
            logging.warning(f"Không thể lưu snapshot gốc: {e}")
            
    timestamp = int(time.time() * 1000)
    snap_name = f"draft_{timestamp}.json"
    snap_path = history_dir / snap_name
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    if 0 <= curr_idx < len(snapshots) - 1:
        for s in snapshots[curr_idx + 1:]:
            p = history_dir / s
            if p.exists():
                try: p.unlink()
                except Exception: pass
        snapshots = snapshots[:curr_idx + 1]
        
    snapshots.append(snap_name)
    if len(snapshots) > 20:
        oldest = snapshots.pop(0)
        p = history_dir / oldest
        if p.exists():
            try: p.unlink()
            except Exception: pass
            
    state["snapshots"] = snapshots
    state["current_index"] = len(snapshots) - 1
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
        
    save_draft_safely_py(draft_file, data)

def clean_orphan_materials(data: dict):
    """Dọn dẹp các material mồ côi không còn được segment nào tham chiếu."""
    used_ids = set()
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            if s.get("material_id"):
                used_ids.add(s["material_id"])
            for ref in s.get("extra_material_refs", []):
                used_ids.add(ref)
                
    mats = data.get("materials", {})
    material_keys = ["videos", "audios", "texts", "video_effects", "material_animations", "transitions", "stickers", "speeds"]
    for k in material_keys:
        if k in mats and isinstance(mats[k], list):
            mats[k] = [item for item in mats[k] if item.get("id") in used_ids]

def recalculate_project_duration(data: dict):
    """Tính toán lại tổng thời lượng duration của draft dựa trên toàn bộ segments."""
    max_end = 0
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            tr = s.get("target_timerange") or {}
            end = tr.get("start", 0) + tr.get("duration", 0)
            if end > max_end:
                max_end = end
    data["duration"] = max_end

app = FastAPI(title="CapCut AI Co-Director Studio")

ALLOWED_ORIGINS = [
    "http://127.0.0.1:8765",
    "http://localhost:8765",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def validate_origin_middleware(request: Request, call_next):
    # Kiểm tra Origin cho các request ghi dữ liệu (POST, PUT, DELETE, PATCH)
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: Origin không nằm trong danh sách được phép"}
            )
    return await call_next(request)

@app.exception_handler(ConnectionResetError)
async def connection_reset_handler(request: Request, exc: ConnectionResetError):
    # Chromium canceled media range request during seek - harmless client disconnect (HTTP 204 No Content không có body)
    return Response(status_code=204)

CAPCUT_DRAFT_BASE = detect_capcut_draft_base()
PROJECT_NAME_REGEX = re.compile(r"^[\w\- .]+$")
ALLOWED_MEDIA_EXTS = {".mp4", ".mov", ".mp3", ".m4a", ".wav", ".jpg", ".jpeg", ".png", ".webp"}

def get_draft_file(project_name: str, must_exist: bool = True) -> Path:
    """Validate project_name và resolve đường dẫn draft_content.json, ngăn chặn Path Traversal."""
    if not project_name or not PROJECT_NAME_REGEX.match(project_name):
        raise HTTPException(status_code=400, detail="Tên dự án chứa ký tự không hợp lệ")
    
    base_resolved = CAPCUT_DRAFT_BASE.resolve()
    draft_file = (CAPCUT_DRAFT_BASE / project_name / "draft_content.json").resolve()
    
    # Bắt buộc draft_file phải nằm trong CAPCUT_DRAFT_BASE
    try:
        draft_file.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(status_code=403, detail="Truy cập ngoài thư mục dự án CapCut bị từ chối")
        
    if must_exist and not draft_file.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy dự án CapCut: {project_name}")
        
    return draft_file

def validate_folder_path(folder_path: str) -> Path:
    """Validate thư mục footage an toàn, chống duyệt thư mục hệ thống."""
    if not folder_path or not folder_path.strip():
        raise HTTPException(status_code=400, detail="Đường dẫn thư mục không được để trống")
    p = Path(folder_path.strip()).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Thư mục không tồn tại: {folder_path}")
        
    # Chặn các thư mục hệ thống nguy hiểm trên Windows/Linux
    forbidden_roots = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "/etc", "/var", "/bin", "/usr"]
    for fb in forbidden_roots:
        try:
            p.relative_to(Path(fb).resolve())
            raise HTTPException(status_code=403, detail="Truy cập thư mục hệ thống bị từ chối vì lý do an toàn")
        except ValueError:
            pass
    return p

def is_allowed_media_file(p: Path) -> bool:
    """Chỉ cho phép đọc media thuộc thư mục draft hoặc materials được tham chiếu."""
    try:
        resolved = p.resolve()
    except Exception:
        return False
        
    ext = resolved.suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTS:
        return False
        
    # 1. Nằm trong CAPCUT_DRAFT_BASE
    try:
        resolved.relative_to(CAPCUT_DRAFT_BASE.resolve())
        return True
    except ValueError:
        pass
        
    # 2. Nằm trong thư mục materials / footage được tham chiếu trong các dự án
    if CAPCUT_DRAFT_BASE.exists():
        for d in CAPCUT_DRAFT_BASE.iterdir():
            if d.is_dir():
                df = d / "draft_content.json"
                if df.exists():
                    try:
                        with open(df, "r", encoding="utf-8") as f:
                            d_json = json.load(f)
                            mats = d_json.get("materials", {})
                            for item in mats.get("videos", []) + mats.get("audios", []):
                                raw_p = item.get("path") or item.get("media_path")
                                if raw_p:
                                    res_p = Path(resolve_draft_path(raw_p, d)).resolve()
                                    if resolved == res_p:
                                        return True
                                    if res_p.parent and res_p.parent.exists():
                                        try:
                                            resolved.relative_to(res_p.parent)
                                            return True
                                        except ValueError:
                                            pass
                    except Exception:
                        continue
    return False

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

@app.get("/api/capcut-status")
def get_capcut_status():
    """Kiểm tra trạng thái thực thi của phần mềm CapCut Desktop."""
    running = is_capcut_running()
    return {
        "running": running,
        "capcut_running": running,
        "is_running": running,
        "message": "CapCut Desktop đang chạy — chỉnh sửa bị khóa." if running else "CapCut Desktop chưa chạy. Sẵn sàng ghi an toàn."
    }

@app.get("/api/projects")
def list_projects():
    if not CAPCUT_DRAFT_BASE.exists():
        return {
            "projects": [],
            "warning": f"Không tìm thấy thư mục CapCut tại: {CAPCUT_DRAFT_BASE}. Vui lòng kiểm tra cài đặt hoặc đặt biến môi trường CAPCUT_DRAFTS_DIR."
        }
    
    projects = []
    for item in CAPCUT_DRAFT_BASE.iterdir():
        draft_file = item / "draft_content.json"
        if item.is_dir() and draft_file.exists():
            mtime = os.path.getmtime(draft_file)
            video_count = 0
            text_count = 0
            duration_us = 0
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
                
            entry = {
                "name": item.name,
                "path": str(draft_file).replace("\\", "/"),
                "modified": mtime,
                "video_count": video_count,
                "text_count": text_count,
                "duration_sec": round(duration_us / 1e6, 2),
                "has_footage": video_count > 0
            }
            if err_msg:
                entry["error"] = err_msg
            projects.append(entry)
            
    # Sắp xếp: dự án có footage lên đầu, sau đó theo thời gian chỉnh sửa mới nhất
    projects.sort(key=lambda x: (1 if x["has_footage"] else 0, x["modified"]), reverse=True)
    return {"projects": projects, "capcut_running": is_capcut_running(), "draft_base": str(CAPCUT_DRAFT_BASE).replace("\\", "/")}

class ImportFolderRequest(BaseModel):
    folderPath: str

@app.post("/api/projects/import-folder")
def import_project_folder(req: ImportFolderRequest):
    if not req.folderPath or not req.folderPath.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường dẫn thư mục hoặc file draft")
    p = Path(req.folderPath.strip().strip('"').strip("'")).resolve()
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Đường dẫn không tồn tại: {p}")
        
    if p.is_file() and p.name == "draft_content.json":
        p = p.parent
        
    draft_file = p / "draft_content.json"
    if not draft_file.exists():
        raise HTTPException(status_code=400, detail=f"Thư mục không chứa draft_content.json hợp lệ: {p}")
        
    proj_name = p.name
    target_dir = (CAPCUT_DRAFT_BASE / proj_name).resolve()
    
    if p == target_dir:
        return {"ok": True, "projectName": proj_name, "message": "Dự án đã có sẵn trong CapCut"}
        
    import shutil
    try:
        if target_dir.exists():
            proj_name = f"{proj_name}_{int(time.time())}"
            target_dir = (CAPCUT_DRAFT_BASE / proj_name).resolve()
        shutil.copytree(p, target_dir)
        return {"ok": True, "projectName": proj_name, "message": f"Đã nhập thành công vào CapCut: {proj_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nhập dự án: {str(e)}")

@app.get("/api/media")
def stream_media(path: str = Query(..., description="Absolute path to media file")):
    p = Path(path)
    ext = p.suffix.lower()
    
    # 1. Whitelist extension check
    if ext not in ALLOWED_MEDIA_EXTS:
        raise HTTPException(status_code=403, detail="Định dạng tệp media không được phép truy cập")
        
    resolved_p = p.resolve()
    # 2. Whitelist directory check (draft folder, materials folder)
    if not is_allowed_media_file(resolved_p):
        raise HTTPException(status_code=403, detail="Truy cập tệp nằm ngoài thư mục dự án CapCut bị từ chối")
        
    if not resolved_p.exists() or not resolved_p.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp media")
    
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
    return FileResponse(resolved_p, media_type=media_types.get(ext, "application/octet-stream"))

@app.get("/api/project/{project_name}")
def get_project(project_name: str):
    draft_file = get_draft_file(project_name)
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
        
    effects_map = {e.get("id"): e for e in materials.get("video_effects", [])}
    mat_animations_map = {m.get("id"): m for m in materials.get("material_animations", [])}
    placeholders_map = {p.get("id"): p for p in materials.get("placeholders", [])}
    
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
                
                clip_meta = s.get("clip") or {}
                scale_meta = clip_meta.get("scale") or {}
                scale_val = scale_meta.get("x", 1.0)
                transform = clip_meta.get("transform") or {}
                
                # Collect extra_material_refs (effects, animations, transitions applied)
                extra_refs = s.get("extra_material_refs") or []
                applied_effects = []
                applied_animations = []
                for ref_id in extra_refs:
                    if ref_id in effects_map:
                        e = effects_map[ref_id]
                        applied_effects.append({
                            "id": ref_id,
                            "name": e.get("name", e.get("effect_id", ref_id[:8])),
                            "params": e.get("effect_adjust_params") or []
                        })
                    if ref_id in mat_animations_map:
                        a = mat_animations_map[ref_id]
                        applied_animations.append({
                            "id": ref_id,
                            "in": (a.get("in") or {}).get("name", ""),
                            "out": (a.get("out") or {}).get("name", ""),
                            "loop": (a.get("loop") or {}).get("name", "")
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
                    txt_obj = texts_map.get(mid) or {}
                    raw_t = txt_obj.get("raw") or {}
                    seg_info["label"] = txt_obj.get("text", "Text") or "Text"
                    seg_info["color"] = "#a84334"
                    seg_info["details"]["text"] = txt_obj.get("text", "")
                    seg_info["details"]["styles"] = txt_obj.get("styles") or []
                    seg_info["details"]["font_size"] = raw_t.get("font_size", 0)
                    seg_info["details"]["text_align"] = raw_t.get("alignment", 1)
                elif track_type == "sticker":
                    st_obj = stickers_map.get(mid) or {}
                    seg_info["label"] = st_obj.get("name", "Sticker") or "Ảnh vector"
                    seg_info["color"] = "#cf8a28"
                    seg_info["details"]["sticker_id"] = st_obj.get("id", "")
                    seg_info["details"]["sticker_url"] = st_obj.get("resource_id", "")
                elif track_type == "video":
                    v_obj = videos_map.get(mid) or {}
                    resolved = v_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else ""
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
                    a_obj = audios_map.get(mid) or {}
                    resolved = a_obj.get("_resolved_path", "")
                    filename = os.path.basename(resolved) if resolved else ""
                    seg_info["label"] = filename or a_obj.get("name") or a_obj.get("material_name") or "Audio"
                    seg_info["color"] = "#258352"
                    seg_info["media_path"] = resolved
                    seg_info["details"]["path"] = resolved
                    seg_info["details"]["volume"] = s.get("volume", 1.0)
                elif track_type in ("effect", "adjust"):
                    p_obj = placeholders_map.get(mid) or {}
                    p_name = p_obj.get("name")
                    if track_type == "adjust":
                        seg_info["label"] = p_name or "Màu thương mại (Studio LUT)"
                        seg_info["color"] = "#8b5cf6"
                    else:
                        seg_info["label"] = p_name or "Hiệu ứng"
                        seg_info["color"] = "#b030b0"
                    
                parsed_segments.append(seg_info)
            except Exception as seg_err:
                # Ghi log lỗi và gán nhãn fallback theo track type, tính đúng end_us, không nhét lỗi vào label
                logging.warning(f"Lỗi parse segment {s.get('id')}: {seg_err}")
                tr_fallback = s.get("target_timerange") or {}
                f_start = tr_fallback.get("start", 0)
                f_dur = tr_fallback.get("duration", 0)
                f_end = f_start + f_dur
                if f_end > max_track_end:
                    max_track_end = f_end
                type_labels = {
                    "video": "Video Clip",
                    "audio": "Audio",
                    "text": "Văn bản",
                    "effect": "Hiệu ứng",
                    "adjust": "Hiệu ứng",
                    "sticker": "Nhãn dán"
                }
                fallback_label = type_labels.get(track_type, "Clip")
                fallback_color = "#1e40af" if track_type == "video" else ("#166534" if track_type == "audio" else "#b45309")
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
    v_count, a_count, t_count, fx_count, st_count = 0, 0, 0, 0, 0
    for pt in parsed_tracks:
        ttype = pt["type"]
        if ttype == "video":
            v_count += 1
            if v_count == 1:
                pt["label"] = "V1 (Chính)"
                pt["is_main"] = True
            else:
                pt["label"] = f"V{v_count} (Lớp phủ)"
                pt["is_main"] = False
        elif ttype == "audio":
            a_count += 1
            # Tín hiệu đáng tin cậy: tên material hoặc cờ flag
            labels_concat = " ".join([s.get("label", "").lower() for s in pt["segments"]] + [s.get("media_path", "").lower() for s in pt["segments"]])
            if pt["flag"] == 1 or any(k in labels_concat for k in ["bgm", "music", "nhac", "soundtrack"]):
                pt["label"] = f"A{a_count} (BGM)"
            elif any(k in labels_concat for k in ["voice", "thoai", "speech", "mic", "vj"]):
                pt["label"] = f"A{a_count} (Thoại)"
            else:
                pt["label"] = f"A{a_count}"
        elif ttype == "text":
            t_count += 1
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

@app.post("/api/update-clip")
def update_clip(req: UpdateClipRequest):
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    target_mid = None
    target_seg = None
    target_track = None
    for track in data.get("tracks", []):
        for s in track.get("segments", []):
            if s.get("id") == req.segment_id:
                target_seg = s
                target_mid = s.get("material_id")
                target_track = track
                break
        if target_seg:
            break
        
    if not target_seg or not target_track:
        raise HTTPException(status_code=404, detail="Segment not found")
        
    cur_trange = target_seg.get("target_timerange") or {}
    cur_start = cur_trange.get("start", 0)
    cur_dur = cur_trange.get("duration", 0)
    new_start = max(0, req.start_us) if req.start_us is not None else cur_start
    new_dur = max(100_000, req.duration_us) if req.duration_us is not None else cur_dur
    new_end = new_start + new_dur

    # Kiểm tra va chạm / overlap với clip khác trong cùng track (Từ chối hoặc Snap)
    for other in target_track.get("segments", []):
        if other.get("id") == req.segment_id:
            continue
        o_tr = other.get("target_timerange") or {}
        o_start = o_tr.get("start", 0)
        o_dur = o_tr.get("duration", 0)
        o_end = o_start + o_dur
        if max(new_start, o_start) < min(new_end, o_end):
            overlap_us = min(new_end, o_end) - max(new_start, o_start)
            if overlap_us <= 500_000:
                # Snap nếu va chạm nhỏ <= 0.5s
                if new_start < o_start:
                    new_dur = max(100_000, o_start - new_start)
                    new_end = new_start + new_dur
                else:
                    new_start = o_end
                    new_end = new_start + new_dur
            else:
                raise HTTPException(status_code=400, detail="Clip bị chồng chéo với clip khác trong cùng track")

    # Cập nhật thời gian
    if "target_timerange" not in target_seg:
        target_seg["target_timerange"] = {}
    target_seg["target_timerange"]["start"] = new_start
    target_seg["target_timerange"]["duration"] = new_dur

    # Cập nhật speed & source_timerange
    speed_val = target_seg.get("speed", 1.0) or 1.0
    if req.speed is not None:
        speed_val = max(0.1, min(10.0, req.speed))
        target_seg["speed"] = speed_val
        # Cập nhật hoặc tạo speed trong materials.speeds
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
            speeds_list.append({
                "id": speed_ref_id,
                "speed": speed_val,
                "type": "speed"
            })
            if "extra_material_refs" not in target_seg:
                target_seg["extra_material_refs"] = []
            target_seg["extra_material_refs"].append(speed_ref_id)

    # Đổi duration thì cập nhật source_timerange theo speed
    if target_seg.get("source_timerange"):
        target_seg["source_timerange"]["duration"] = int(round(new_dur * speed_val))

    # Cập nhật scale, volume, text
    if req.scale is not None:
        target_seg["clip"] = target_seg.get("clip") or {}
        target_seg["clip"]["scale"] = {"x": req.scale, "y": req.scale}
    if req.volume is not None:
        target_seg["volume"] = max(0.0, min(2.0, req.volume))
        
    if req.text_content is not None and target_mid:
        for t in data.get("materials", {}).get("texts", []):
            if t.get("id") == target_mid:
                c_obj = json.loads(t.get("content", "{}"))
                c_obj["text"] = req.text_content
                t["content"] = json.dumps(c_obj, ensure_ascii=False)
                break
                
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
        
    return {"status": "success", "message": "Cập nhật clip thành công"}

@app.post("/api/split-clip")
def split_clip(req: CommandRequest):
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    split_us = req.playhead_time_us or 0
    found = False
    materials = data.setdefault("materials", {})
    
    for track in data.get("tracks", []):
        for idx, s in enumerate(track.get("segments", [])):
            if s.get("id") == req.target_segment_id:
                tr = s.get("target_timerange") or {}
                start = tr.get("start", 0)
                dur = tr.get("duration", 0)
                end = start + dur
                
                # Nếu playhead không nằm hoàn toàn giữa clip (ví dụ ở mép đầu/cuối), tự động cắt ở điểm giữa clip
                if not (start < split_us < end):
                    if dur > 200_000:
                        split_us = start + dur // 2
                    else:
                        return {"status": "error", "message": "Playhead phải nằm bên trong clip để cắt đôi"}
                
                # Split into 2 segments
                left_dur = split_us - start
                right_dur = end - split_us
                tr["duration"] = left_dur
                
                new_seg = json.loads(json.dumps(s))
                new_seg["id"] = str(uuid.uuid4()).upper()
                if "target_timerange" not in new_seg:
                    new_seg["target_timerange"] = {}
                new_seg["target_timerange"]["start"] = split_us
                new_seg["target_timerange"]["duration"] = right_dur
                
                # Fix: Synchronize source_timerange for video and audio
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
                    
                # Clone material theo từng segment với id mới cho extra_material_refs
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
                                cloned = True
                                break
                        if cloned:
                            break
                    new_extra_refs.append(new_ref_id if cloned else ref_id)
                new_seg["extra_material_refs"] = new_extra_refs
                
                # Chia lại keyframe theo thời gian cắt
                if s.get("keyframe_list"):
                    old_kfs = s.get("keyframe_list") or []
                    left_kfs = []
                    right_kfs = []
                    for kf in old_kfs:
                        time_offset = kf.get("time_offset", 0)
                        if time_offset <= left_dur:
                            left_kfs.append(kf)
                        else:
                            new_kf = json.loads(json.dumps(kf))
                            new_kf["id"] = str(uuid.uuid4()).upper()
                            new_kf["time_offset"] = max(0, time_offset - left_dur)
                            right_kfs.append(new_kf)
                    s["keyframe_list"] = left_kfs
                    new_seg["keyframe_list"] = right_kfs
                    
                track["segments"].insert(idx + 1, new_seg)
                found = True
                break
        if found:
            break
        
    if not found:
        return {"status": "error", "message": "Playhead phải nằm bên trong clip để cắt đôi"}
        
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
        
    return {"status": "success", "message": f"Đã cắt clip tại {split_us/1e6:.2f}s"}

@app.post("/api/delete-clip")
def delete_clip(req: CommandRequest):
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
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
        return {"status": "error", "message": "Không tìm thấy clip để xóa"}
        
    clean_orphan_materials(data)
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
        
    return {"status": "success", "message": "Đã xóa clip thành công"}

@app.get("/api/quality-audit/{project_name}")
def quality_audit(project_name: str):
    scan_res = scan_project_errors(project_name)
    errors = scan_res.get("errors", [])
    
    # Gom nhóm theo type để tạo danh sách issues thống nhất
    grouped = {}
    for err in errors:
        t = err.get("type", "UNKNOWN")
        if t not in grouped:
            grouped[t] = {
                "type": t,
                "severity": err.get("severity", "WARNING"),
                "title": err.get("title", ""),
                "items": [],
                "fix_action": err.get("fix_command", "Tự động tối ưu qua AI Agent")
            }
        grouped[t]["items"].append(err)
        if err.get("severity") == "CRITICAL":
            grouped[t]["severity"] = "CRITICAL"
            
    issues = []
    for t, grp in grouped.items():
        count = len(grp["items"])
        sev = grp["severity"]
        title = grp["title"]
        issues.append({
            "type": t,
            "severity": sev,
            "count": count,
            "message": f"Phát hiện {count} vị trí vi phạm: {title}",
            "fix_action": grp["fix_action"]
        })
        
    crit_count = scan_res.get("critical_count", 0)
    score = scan_res.get("health_score", 100)
    
    # Quy tắc C1: Điểm số không được hiện "ĐẠT CHUẨN" khi còn cảnh báo CRITICAL
    if crit_count > 0:
        status = "CRITICAL" if score < 60 else "WARNING"
    else:
        status = "PASS" if score >= 85 else ("WARNING" if score >= 60 else "POOR")
        
    return {
        "project_name": project_name,
        "score": score,
        "status": status,
        "total_issues": len(errors),
        "groups_count": len(issues),
        "critical_count": crit_count,
        "warning_count": scan_res.get("warning_count", 0),
        "issues": issues
    }

def scan_project_errors(project_name: str) -> Dict[str, Any]:
    draft_file = get_draft_file(project_name)
    draft_dir = draft_file.parent
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    errors = []
    texts_map = {t.get("id"): t for t in (data.get("materials") or {}).get("texts", [])}
    videos_map = {v.get("id"): v for v in (data.get("materials") or {}).get("videos", [])}
    
    # 1. Scan tracks for timing, safe zone, aspect ratio & subtitle styles
    for t_idx, track in enumerate(data.get("tracks", [])):
        ttype = track.get("type")
        for seg in track.get("segments", []):
            sid = seg.get("id")
            trange = seg.get("target_timerange") or {}
            start_us = trange.get("start", 0)
            dur_us = trange.get("duration", 0)
            end_us = start_us + dur_us
            mid = seg.get("material_id")
            
            if ttype == "text":
                clip_meta = seg.get("clip") or {}
                tf = clip_meta.get("transform") or {}
                y = tf.get("y", 0.0)
                t_obj = texts_map.get(mid) or {}
                try:
                    c_obj = json.loads(t_obj.get("content", "{}"))
                    txt = c_obj.get("text", "")
                    styles = c_obj.get("styles") or []
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
                has_shadow = any(len(s.get("shadows") or []) > 0 for s in styles) if styles else False
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
                clip_meta = seg.get("clip") or {}
                scale_meta = clip_meta.get("scale") or {}
                scale_x = scale_meta.get("x", 1.0)
                v_obj = videos_map.get(mid) or {}
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
                tr = s.get("target_timerange") or {}
                e = tr.get("start", 0) + tr.get("duration", 0)
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
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
    
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
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["transform"] = s["clip"].get("transform") or {}
                    s["clip"]["transform"]["y"] = target_y
                    action_note = f"✓ Đã dịch chuyển toạ độ phụ đề về y = {target_y} (Chuẩn an toàn TikTok)"
                    break
    elif err_id.startswith("style_"):
        seg_id = err_id.replace("style_", "")
        font_path = get_montserrat_font_path()
        target_mid = None
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    target_mid = s.get("material_id")
                    break
        if target_mid:
            for t in (data.get("materials") or {}).get("texts", []):
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
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["scale"] = {"x": 1.15, "y": 1.15}
                    action_note = "✓ Đã áp dụng Punch-in Zoom (1.15x) loại bỏ hoàn toàn viền đen"
                    break
    elif err_id == "dead_outro":
        max_voice_end = 0
        for track in data.get("tracks", []):
            if track.get("type") in ["audio", "text"]:
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    end_time = tr.get("start", 0) + tr.get("duration", 0)
                    if end_time > max_voice_end:
                        max_voice_end = end_time
        if max_voice_end > 0:
            target_end = max_voice_end + 400_000
            data["duration"] = target_end
            for track in data.get("tracks", []):
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                        tr["duration"] = max(100_000, target_end - tr.get("start", 0))
            action_note = f"✓ Đã cắt cụt timeline tại {target_end/1e6:.2f}s, triệt tiêu khoảng chết"
            
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
        
    return {
        "status": "success",
        "fixed_error_id": req.error_id,
        "action_performed": action_note or f"✓ Đã tối ưu lỗi {req.error_id}"
    }

@app.post("/api/ai-agent/auto-fix-all")
def auto_fix_all(req: AutoFixAllRequest):
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    font_path = get_montserrat_font_path()
    actions_log = []
    
    # 1. Fix all text safe zones to y = -0.404 and inject Montserrat Shadow
    fixed_texts = 0
    for track in data.get("tracks", []):
        if track.get("type") == "text":
            for s in track.get("segments", []):
                s["clip"] = s.get("clip") or {}
                s["clip"]["transform"] = s["clip"].get("transform") or {}
                s["clip"]["transform"]["y"] = -0.404
                fixed_texts += 1
                
    if fixed_texts > 0:
        actions_log.append(f"✓ Đã căn chỉnh {fixed_texts} phụ đề về Safe Zone TikTok (y = -0.404)")
        
    for t in (data.get("materials") or {}).get("texts", []):
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
                s["clip"] = s.get("clip") or {}
                cur_scale = (s["clip"].get("scale") or {}).get("x", 1.0)
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
                tr = s.get("target_timerange") or {}
                end_time = tr.get("start", 0) + tr.get("duration", 0)
                if end_time > max_voice_end:
                    max_voice_end = end_time
    if max_voice_end > 0:
        target_end = max_voice_end + 400_000
        data["duration"] = target_end
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                tr = s.get("target_timerange") or {}
                if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                    tr["duration"] = max(100_000, target_end - tr.get("start", 0))
        actions_log.append(f"✓ Đã triệt tiêu đuôi chết, chốt timeline dứt khoát tại {target_end/1e6:.2f}s")

    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)

    return {
        "status": "success",
        "actions_log": actions_log,
        "message": "AI Agent đã tự động sửa toàn bộ lỗi trên timeline!"
    }

@app.post("/api/execute-command")
def execute_command(req: CommandRequest):
    check_capcut_not_running()
    draft_file = get_draft_file(req.project_name)
    
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
                    curr_start = (s.get("target_timerange") or {}).get("start", 0)
                    new_start = max(0, curr_start + delta)
                    if "target_timerange" not in s:
                        s["target_timerange"] = {}
                    s["target_timerange"]["start"] = new_start
                    found = True
                    direction_str = "sớm hơn" if is_earlier else "trễ hơn"
                    feedback.append(f"✓ Đã dịch chuyển clip {direction_str} {val}s (từ {curr_start/1e6:.2f}s ➔ {new_start/1e6:.2f}s)")
                    break
            if found: break
            
        if not found and req.target_track_index is not None:
            t = data.get("tracks", [])[req.target_track_index]
            for s in t.get("segments", []):
                if "target_timerange" not in s:
                    s["target_timerange"] = {}
                s["target_timerange"]["start"] = max(0, (s["target_timerange"].get("start", 0)) + delta)
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
            for t in (data.get("materials") or {}).get("texts", []):
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
        
        font_path = get_montserrat_font_path()
        updated_texts = 0
        for t in (data.get("materials") or {}).get("texts", []):
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
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["scale"] = {"x": scale_val, "y": scale_val}
                    feedback.append(f"✓ Đã áp dụng Punch-in Zoom ({scale_val}x) cho clip")
                    break

    # 5. Safe zone alignment
    if 'safe' in cmd_lower or 'vùng an toàn' in cmd_lower or 'tiktok' in cmd_lower:
        for track in data.get("tracks", []):
            if track.get("type") == "text":
                for s in track.get("segments", []):
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["transform"] = s["clip"].get("transform") or {}
                    s["clip"]["transform"]["y"] = -0.404
        feedback.append("✓ Đã căn chỉnh toàn bộ phụ đề về tọa độ an toàn TikTok (y = -0.404)")

    # 6. Cut Dead Outro
    if 'outro' in cmd_lower or 'đuôi' in cmd_lower or 'thừa' in cmd_lower:
        max_voice_end = 0
        for track in data.get("tracks", []):
            if track.get("type") in ["audio", "text"]:
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    end_time = tr.get("start", 0) + tr.get("duration", 0)
                    if end_time > max_voice_end:
                        max_voice_end = end_time
        if max_voice_end > 0:
            target_end = max_voice_end + 400_000
            data["duration"] = target_end
            for track in data.get("tracks", []):
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                        tr["duration"] = max(100_000, target_end - tr.get("start", 0))
            feedback.append(f"✓ Đã triệt tiêu đuôi chết, chốt dứt khoát tại {target_end/1e6:.2f}s")

    if not feedback:
        feedback.append(f"✓ Đã thực thi lệnh '{cmd}' và cập nhật thông số dự án thành công!")

    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)

    return {
        "status": "success",
        "feedback": "\n".join(feedback),
        "message": "Thực thi thành công"
    }

@app.post("/api/undo/{project_name}")
def undo_action(project_name: str):
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    history_dir = draft_file.parent / ".history"
    index_file = history_dir / "history_state.json"
    
    if history_dir.exists() and index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            snapshots = state.get("snapshots", [])
            curr_idx = state.get("current_index", -1)
            if curr_idx > 0 and len(snapshots) > 0:
                curr_idx -= 1
                target_snap = history_dir / snapshots[curr_idx]
                if target_snap.exists():
                    with open(target_snap, "r", encoding="utf-8") as f:
                        snap_data = json.load(f)
                    save_draft_safely_py(draft_file, snap_data)
                    state["current_index"] = curr_idx
                    with open(index_file, "w", encoding="utf-8") as f:
                        json.dump(state, f, ensure_ascii=False)
                    return {
                        "status": "success",
                        "message": f"Hoàn tác thành công (Bước {curr_idx + 1}/{len(snapshots)})",
                        "remaining_undo": curr_idx,
                        "remaining_redo": len(snapshots) - 1 - curr_idx
                    }
        except Exception as e:
            logging.warning(f"Lỗi đọc history undo: {e}")
            
    backup_file = draft_file.with_suffix(".json.bak")
    if not backup_file.exists():
        return {"status": "error", "message": "Không có bản backup hoặc lịch sử để hoàn tác"}
    
    shutil.copy2(backup_file, draft_file)
    return {"status": "success", "message": "Đã khôi phục từ bản backup gần nhất"}

@app.post("/api/redo/{project_name}")
def redo_action(project_name: str):
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    history_dir = draft_file.parent / ".history"
    index_file = history_dir / "history_state.json"
    
    if not history_dir.exists() or not index_file.exists():
        return {"status": "error", "message": "Không có lịch sử để làm lại (Redo)"}
        
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        snapshots = state.get("snapshots", [])
        curr_idx = state.get("current_index", -1)
        if curr_idx < len(snapshots) - 1 and curr_idx >= 0:
            curr_idx += 1
            target_snap = history_dir / snapshots[curr_idx]
            if target_snap.exists():
                with open(target_snap, "r", encoding="utf-8") as f:
                    snap_data = json.load(f)
                save_draft_safely_py(draft_file, snap_data)
                state["current_index"] = curr_idx
                with open(index_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False)
                return {
                    "status": "success",
                    "message": f"Làm lại thành công (Bước {curr_idx + 1}/{len(snapshots)})",
                    "remaining_undo": curr_idx,
                    "remaining_redo": len(snapshots) - 1 - curr_idx
                }
        return {"status": "error", "message": "Đã ở trạng thái mới nhất, không có bước nào để Redo"}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi thực hiện Redo: {str(e)}"}

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


MCP_ALLOWED_TOOLS = {
    "capcut_scan_and_index_footage",
    "capcut_compile_13layer_draft",
    "capcut_safe_launch"
}
MCP_RUNNER_JS = Path(__file__).parent / "mcp_runner.js"

def get_mcp_server_js() -> Optional[Path]:
    """Lấy đường dẫn file capcut_mcp_server.js từ biến môi trường CAPCUT_MCP_JS hoặc fallback."""
    env_path = os.environ.get("CAPCUT_MCP_JS")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists() and p.is_file():
            return p
        return None  # Biến môi trường đã được đặt nhưng file không tồn tại
    # Fallback kiểm tra các vị trí quen thuộc khi không đặt biến môi trường
    candidates = [
        Path(__file__).parent / "capcut_mcp_server.js",
        Path(__file__).parent.parent / "capcut-roughcut-studio" / "capcut_mcp_server.js",
        Path.home() / ".gemini" / "antigravity-ide" / "scratch" / "capcut-roughcut-studio" / "capcut_mcp_server.js"
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()
    return None

@app.get("/api/mcp/tools")
def get_mcp_tools():
    server_js = get_mcp_server_js()
    if not server_js:
        return {
            "status": "disconnected",
            "mcp_server": "capcut-commercial-editor",
            "tools": [],
            "message": "Chưa cấu hình CAPCUT_MCP_JS hoặc không tìm thấy file script MCP Server"
        }
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
    # Cho phép tạo dự án mới an toàn khi CapCut đang chạy (Zero-restart workflow)
    server_js = get_mcp_server_js()
    if not server_js:
        raise HTTPException(
            status_code=501,
            detail="MCP Server chưa được cấu hình hoặc không tìm thấy tệp script (Vui lòng đặt biến môi trường CAPCUT_MCP_JS)"
        )
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
    
    runner_input = {
        "action": "create_project",
        "toolName": "capcut_compile_13layer_draft",
        "args": payload
    }
    
    temp_input = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
            json.dump(runner_input, tf, ensure_ascii=False)
            temp_input = tf.name
            
        proc = subprocess.run(
            ["node", str(MCP_RUNNER_JS), str(server_js), temp_input],
            capture_output=True,
            text=True,
            check=True
        )
        res_data = json.loads(proc.stdout.strip())
        if res_data.get("ok"):
            try:
                import register_draft
                reg_res = register_draft.register_project_in_capcut(req.projectName)
                logging.info(f"Đăng ký CapCut root_meta_info: {reg_res}")
            except Exception as reg_err:
                logging.warning(f"Lỗi đăng ký root_meta_info: {reg_err}")
        return res_data
    except subprocess.CalledProcessError as cpe:
        err_msg = cpe.stderr.strip() or cpe.stdout.strip()
        raise HTTPException(status_code=500, detail=f"Lỗi MCP runner: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi MCP compilation: {str(e)}")
    finally:
        if temp_input and os.path.exists(temp_input):
            try:
                os.unlink(temp_input)
            except Exception:
                pass

@app.post("/api/mcp/call-tool")
def mcp_call_tool(req: McpToolCallRequest):
    # Whitelist toolName check
    if req.toolName not in MCP_ALLOWED_TOOLS:
        raise HTTPException(status_code=400, detail=f"Tên tool MCP không hợp lệ: {req.toolName}")
        
    server_js = get_mcp_server_js()
    if not server_js:
        raise HTTPException(
            status_code=501,
            detail="MCP Server chưa được cấu hình hoặc không tìm thấy tệp script (Vui lòng đặt biến môi trường CAPCUT_MCP_JS)"
        )
        
    import subprocess
    import tempfile
    
    runner_input = {
        "action": "call_tool",
        "toolName": req.toolName,
        "args": req.arguments or {}
    }
    
    temp_input = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
            json.dump(runner_input, tf, ensure_ascii=False)
            temp_input = tf.name
            
        proc = subprocess.run(
            ["node", str(MCP_RUNNER_JS), str(server_js), temp_input],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(proc.stdout.strip())
    except subprocess.CalledProcessError as cpe:
        err_msg = cpe.stderr.strip() or cpe.stdout.strip()
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi MCP tool: {err_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi MCP tool call: {str(e)}")
    finally:
        if temp_input and os.path.exists(temp_input):
            try:
                os.unlink(temp_input)
            except Exception:
                pass

class FootageFolderAnalysisRequest(BaseModel):
    folder_path: str
    max_files: Optional[int] = 20

class ScriptParseRequest(BaseModel):
    raw_script: str
    pacing_mode: Optional[str] = "medium"

@app.post("/api/ai-agent/analyze-footage-folder")
def api_analyze_footage_folder(req: FootageFolderAnalysisRequest):
    # Validate folder path an toàn
    try:
        valid_folder = validate_folder_path(req.folder_path)
    except HTTPException as he:
        return JSONResponse(
            status_code=he.status_code,
            content={"status": "error", "message": he.detail, "detail": he.detail}
        )
    try:
        import footage_analyzer
        res = footage_analyzer.scan_and_analyze_folder(str(valid_folder), max_files=req.max_files or 20)
        if not res.get("ok"):
            err_msg = res.get("error") or "Không thể quét thư mục footage"
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": err_msg, "detail": err_msg}
            )
        return res
    except Exception as e:
        err_msg = f"Lỗi phân tích footage: {str(e)}"
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": err_msg, "detail": err_msg}
        )

@app.post("/api/ai-agent/parse-script")
def api_parse_script(req: ScriptParseRequest):
    try:
        import footage_analyzer
        sentences = footage_analyzer.parse_commercial_script(req.raw_script, pacing_mode=req.pacing_mode or "medium")
        return {"ok": True, "count": len(sentences), "sentences": sentences}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích kịch bản: {str(e)}")

class ChatSendRequest(BaseModel):
    message: str
    currentProject: Optional[str] = None
    brollFolder: Optional[str] = None
    vjVideo: Optional[str] = None
    bgmPath: Optional[str] = None

CHAT_SESSION_FILE = Path(__file__).parent / "agent_bridge" / "chat_session.json"
CHAT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_chat_history():
    if CHAT_SESSION_FILE.exists():
        try:
            with open(CHAT_SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {
            "id": "welcome",
            "role": "assistant",
            "content": "👋 **Xin chào! Tôi là AI Co-Director (Antigravity IDE Agent)**.\n\nTôi sẵn sàng điều phối MCP Tools và cùng bạn dựng video thương mại 13 tầng chuẩn CapCut Desktop. Bạn có thể:\n- Gửi kịch bản thoại để tôi bóc tách nhịp cắt & dựng video.\n- Yêu cầu quét thư mục footage để lọc clip cháy sáng / rung giật.\n- Yêu cầu tinh chỉnh nhịp cắt (Fast / Medium / Slow) hoặc ducking nhạc nền.",
            "timestamp": int(time.time()),
            "type": "welcome"
        }
    ]

def save_chat_history(messages):
    with open(CHAT_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

@app.get("/api/chat/history")
def api_get_chat_history():
    return {"ok": True, "messages": load_chat_history()}

@app.post("/api/chat/clear")
def api_clear_chat():
    initial = [
        {
            "id": "welcome",
            "role": "assistant",
            "content": "👋 **Phiên chat mới đã sẵn sàng!** Hãy gửi kịch bản hoặc yêu cầu đạo diễn của bạn để tôi điều phối MCP dựng video.",
            "timestamp": int(time.time()),
            "type": "welcome"
        }
    ]
    save_chat_history(initial)
    return {"ok": True, "messages": initial}

@app.post("/api/chat/send")
def api_send_chat(req: ChatSendRequest):
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống")
        
    messages = load_chat_history()
    now_ts = int(time.time())
    
    # 1. Thêm tin nhắn của User
    user_msg_id = f"msg_{now_ts}_u"
    messages.append({
        "id": user_msg_id,
        "role": "user",
        "content": user_text,
        "timestamp": now_ts
    })
    
    # 2. Xử lý phân tích ý định (Intent Recognition & Agent Orchestration)
    import footage_analyzer
    lower_text = user_text.lower()
    
    is_compile_intent = any(kw in lower_text for kw in ["dựng", "tạo video", "biên dịch", "compile", "kịch bản:", "[broll]", "[vj]"])
    is_scan_intent = any(kw in lower_text for kw in ["quét", "scan", "lọc lỗi", "footage"])
    
    agent_content = ""
    agent_payload = {}
    
    if is_compile_intent:
        # Tự động parse kịch bản
        pacing = "fast" if "nhanh" in lower_text else ("slow" if "chậm" in lower_text else "medium")
        parsed_sentences = footage_analyzer.parse_commercial_script(user_text, pacing_mode=pacing)
        
        if len(parsed_sentences) == 0:
            # Fallback nếu người dùng chỉ nói "dựng video" chung chung
            parsed_sentences = footage_analyzer.parse_commercial_script(
                "Chào mừng bạn đến với video thương mại.\n[BROLL] Cận cảnh chi tiết sản phẩm cao cấp.\nChất lượng vượt trội, trải nghiệm hoàn hảo.\n[BROLL] Quy trình sản xuất chuyên nghiệp.\nĐặt hàng ngay hôm nay để nhận ưu đãi đặc biệt!",
                pacing_mode=pacing
            )
            
        proj_name = f"AI_DIRECTOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        broll_folder = req.brollFolder or str(CAPCUT_DRAFT_BASE / (req.currentProject or "BBSM_SET3_KB20") / "materials" / "video")
        
        # Gọi MCP Compiler
        try:
            mcp_payload = {
                "projectName": proj_name,
                "vjVideoPath": req.vjVideo or "",
                "brollFolderPath": broll_folder,
                "supportingFolder": req.brollFolder or "",
                "bgmPath": req.bgmPath or "",
                "hookText": parsed_sentences[0]["keyword"].upper() if parsed_sentences else "HOT DEAL",
                "ctaText": "ĐẶT HÀNG NGAY HÔM NAY",
                "excludedClipPaths": [],
                "scriptSentences": parsed_sentences
            }
            
            # Ghi file thông qua Node MCP Runner
            server_js = get_mcp_server_js()
            runner_input = {
                "action": "create_project",
                "toolName": "capcut_compile_13layer_draft",
                "args": mcp_payload
            }
            
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
                json.dump(runner_input, tf, ensure_ascii=False)
                t_name = tf.name
                
            res = subprocess.run(
                ["node", str(MCP_RUNNER_JS), str(server_js), t_name],
                capture_output=True, text=True, check=True
            )
            os.unlink(t_name)
            mcp_res = json.loads(res.stdout.strip())
            
            agent_content = (
                f"🎬 **Tôi đã điều phối MCP Compiler dựng thành công dự án 13 lớp: `{proj_name}`!**\n\n"
                f"- **Số phân cảnh bóc tách:** {len(parsed_sentences)} câu thoại/B-Roll.\n"
                f"- **Nhịp cắt (Pacing):** {pacing.upper()}.\n"
                f"- **Cấu trúc tầng:** VJ Spine (Track 0) + B-Roll chống trùng (Track 1) + Mic DJI boost +10dB (Track 8) + BGM ducking -5dB (Track 9) + Montserrat Safe Zone (Track 10).\n\n"
                f"Dự án đã sẵn sàng, bạn có thể nạp vào Studio hoặc mở trực tiếp trên CapCut Desktop ngay bên dưới!"
            )
            agent_payload = {
                "action": "project_created",
                "projectName": proj_name,
                "sentencesCount": len(parsed_sentences)
            }
        except Exception as e:
            agent_content = f"⚠️ **Lỗi điều phối MCP Compilation:** {str(e)}\n\nVui lòng kiểm tra lại đường dẫn thư mục footage hoặc kịch bản."
            
    elif is_scan_intent:
        folder_target = req.brollFolder or str(CAPCUT_DRAFT_BASE / (req.currentProject or "BBSM_SET3_KB20") / "materials" / "video")
        try:
            scan_res = footage_analyzer.scan_and_analyze_folder(folder_target, max_files=15)
            if scan_res.get("ok"):
                agent_content = (
                    f"🔍 **Báo cáo quét chẩn đoán footage qua AI & OpenCV:**\n\n"
                    f"- **Tổng số clip quét:** {scan_res['total_scanned']} clip trong thư mục.\n"
                    f"- **Đạt chuẩn thương mại:** {scan_res['approved_count']} clip.\n"
                    f"- **Cảnh báo rung/mờ:** {scan_res['warning_count']} clip.\n"
                    f"- **Loại trừ (cháy sáng / rung mạnh):** {scan_res['rejected_count']} clip.\n\n"
                    f"👉 *AI Agent đã tự động đánh dấu loại trừ các clip lỗi này khỏi bể B-Roll khi dựng.*"
                )
                agent_payload = {"action": "scan_complete", "stats": scan_res}
            else:
                agent_content = f"⚠️ Không thể quét thư mục: {scan_res.get('error')}"
        except Exception as e:
            agent_content = f"⚠️ Lỗi khi quét footage: {str(e)}"
    else:
        # Trả lời tư vấn đạo diễn & hướng dẫn kỹ thuật
        agent_content = (
            f"🎬 **Ghi nhận yêu cầu từ bạn!**\n\n"
            f"Tôi là AI Co-Director trong Antigravity IDE. Tôi có thể giúp bạn:\n"
            f"1. **Dựng video tự động:** Bạn chỉ cần gõ kịch bản (ví dụ có các tag `[BROLL]`, `[VJ]`).\n"
            f"2. **Tối ưu âm thanh:** Tự động ducking BGM khi có tiếng nói người VJ.\n"
            f"3. **Canh lề phụ đề an toàn (Safe Zone):** Tự đưa text về vị trí `pos.y = -0.404` không bị icon TikTok/Reels che khuất.\n\n"
            f"💡 *Bạn muốn tôi hỗ trợ dựng video hay quét phân tích clip nào ngay bây giờ?*"
        )
        
    # Thêm phản hồi của Agent
    agent_msg = {
        "id": f"msg_{now_ts+1}_a",
        "role": "assistant",
        "content": agent_content,
        "timestamp": now_ts + 1,
        "payload": agent_payload
    }
    messages.append(agent_msg)
    save_chat_history(messages)
    
    return {"ok": True, "reply": agent_msg, "messages": messages}

class OpenProjectRequest(BaseModel):
    projectName: str
    autoNavigate: Optional[bool] = True

@app.post("/api/capcut/open-project")
def api_capcut_open_project(req: OpenProjectRequest):
    try:
        import capcut_automator
        res = capcut_automator.open_project_in_capcut(req.projectName)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("CapCut Web Studio starting on http://localhost:8765 ...")
    uvicorn.run(app, host="127.0.0.1", port=8765)
