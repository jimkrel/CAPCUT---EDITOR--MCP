import os
import re

server_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\server.py"
with open(server_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add save_draft_safely_py function after resolve_draft_path
helper_code = '''def resolve_draft_path(raw_path: str, draft_dir: Path) -> str:
    """Resolve CapCut ##_draftpath_placeholder_UUID_## to the actual draft folder path."""
    if not raw_path:
        return ""
    m = re.search(r'##_draftpath_placeholder_[^#]+_##', raw_path)
    if m:
        placeholder = m.group(0)
        resolved = raw_path.replace(placeholder, str(draft_dir).replace('\\\\', '/'))
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
'''

text = re.sub(
    r'def resolve_draft_path\(.*?\n    return raw_path\n',
    helper_code,
    text,
    flags=re.DOTALL
)

# 2. Update split_clip implementation
old_split = '''@app.post("/api/split-clip")
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
                    track["segments"].insert(idx + 1, new_seg)
                    found = True
                    break
        if found: break
        
    if not found:
        return {"status": "error", "message": "Playhead must be inside the selected clip to split"}
        
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": f"Split clip successfully at {split_us/1e6:.2f}s"}'''

new_split = '''@app.post("/api/split-clip")
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
        
    return {"status": "success", "message": f"Split clip successfully at {split_us/1e6:.2f}s"}'''

text = text.replace(old_split, new_split)

# 3. Update McpCreateProjectRequest and mcp_create_project
old_mcp_req = '''class McpCreateProjectRequest(BaseModel):
    projectName: str
    vjVideoPath: Optional[str] = None
    vjAudioWavPath: Optional[str] = None
    brollFolderPath: Optional[str] = None
    bgmPath: Optional[str] = None
    scriptSentences: List[Dict[str, Any]]'''

new_mcp_req = '''class McpCreateProjectRequest(BaseModel):
    projectName: str
    vjVideoPath: Optional[str] = None
    vjAudioWavPath: Optional[str] = None
    brollFolderPath: Optional[str] = None
    bgmPath: Optional[str] = None
    hookText: Optional[str] = None
    ctaText: Optional[str] = None
    scriptSentences: List[Dict[str, Any]]'''

text = text.replace(old_mcp_req, new_mcp_req)

old_payload = '''    payload = {
        "projectName": req.projectName,
        "vjVideoPath": req.vjVideoPath or "",
        "vjAudioWavPath": req.vjAudioWavPath or "",
        "brollFolderPath": req.brollFolderPath or "",
        "bgmPath": req.bgmPath or "",
        "scriptSentences": req.scriptSentences
    }'''

new_payload = '''    payload = {
        "projectName": req.projectName,
        "vjVideoPath": req.vjVideoPath or "",
        "vjAudioWavPath": req.vjAudioWavPath or "",
        "brollFolderPath": req.brollFolderPath or "",
        "bgmPath": req.bgmPath or "",
        "hookText": req.hookText or "",
        "ctaText": req.ctaText or "",
        "scriptSentences": req.scriptSentences
    }'''

text = text.replace(old_payload, new_payload)

# 4. Replace write in update_clip & delete_clip
text = text.replace(
'''    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": "Clip updated successfully"}''',
'''    save_draft_safely_py(draft_file, data)
        
    return {"status": "success", "message": "Clip updated successfully"}'''
)

text = text.replace(
'''    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": "Clip deleted successfully"}''',
'''    save_draft_safely_py(draft_file, data)
        
    return {"status": "success", "message": "Clip deleted successfully"}'''
)

with open(server_path, "w", encoding="utf-8") as f:
    f.write(text)

print("SERVER.PY PATCHED SUCCESSFULLY!")
