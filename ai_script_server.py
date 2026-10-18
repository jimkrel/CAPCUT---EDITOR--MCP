"""
ai_script_server.py - Backend API cho AI Script-to-CapCut Web App
==================================================================
POST /api/build   → nhận footage_folder + script → build draft + launch CapCut
GET  /api/status  → SSE stream: log tiến trình real-time
GET  /api/scan    → quét folder lấy danh sách file footage
"""

import os, sys, json, uuid, shutil, time, threading, asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

app = FastAPI(title="AI CapCut Script Editor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── SSE log queue ────────────────────────────────────────────────────────────
_log_queue: list[dict] = []
_log_lock = threading.Lock()
_build_status = {"running": False, "done": False, "error": None, "result": None}

def log_push(msg: str, level: str = "info", step: int = 0, total: int = 6):
    with _log_lock:
        _log_queue.append({
            "t": time.strftime("%H:%M:%S"),
            "msg": msg, "level": level,
            "step": step, "total": total
        })
    print(f"[{level.upper()}] {msg}")

# ─── MODELS ──────────────────────────────────────────────────────────────────
class ScriptScene(BaseModel):
    text: str
    voice_start: float       # giây bắt đầu trong file WAV
    voice_dur:   float       # độ dài câu thoại (giây)
    aroll_src:   float = 0.0 # thời điểm cắt trong A-Roll
    broll_file:  Optional[str] = None  # tên file B-Roll (trong footage_folder/broll)
    broll_delay: float = 0.0
    broll_dur:   float = 0.0

class BuildRequest(BaseModel):
    project_name:   str
    footage_folder: str          # đường dẫn thư mục chứa toàn bộ footage
    voice_file:     str          # tên file WAV (trong footage_folder)
    bgm_file:       Optional[str] = None
    hook_text:      str = ""
    scenes:         List[ScriptScene]
    launch_capcut:  bool = True

class ScanRequest(BaseModel):
    folder_path: str

# ─── UTILITIES ───────────────────────────────────────────────────────────────
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
REF_DIR       = CAPCUT_DRAFTS / "1017"
WIN_FONTS     = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts"
FONT_BOLD     = str(WIN_FONTS / "Montserrat-Bold.otf").replace("\\", "/") if (WIN_FONTS / "Montserrat-Bold.otf").exists() else ""

def uuidv4(): return str(uuid.uuid4()).upper()

def spd(mats, v=1.0):
    sid = uuidv4()
    mats["speeds"].append({"id": sid, "mode": 0, "speed": float(v), "type": "speed"})
    return sid

def cvs(mats):
    cid = uuidv4()
    mats["canvases"].append({"id": cid, "type": "canvas_color", "color": "#00000000"})
    return cid

def make_subtitle_mat(mats, text: str):
    mid = uuidv4()
    co = {"text": text, "styles": [{"fill": {"content": {"render_type": "solid", "solid": {"color": [1,1,1]}}}, "font": {"path": FONT_BOLD, "id": ""}, "size": 9.5, "bold": True, "shadows": [{"angle": -45, "thickness_projection_angle": -45, "thickness_projection_enable": False, "diffuse": 0.025, "alpha": 0.72, "distance": 5.0, "content": {"render_type": "solid", "solid": {"color": [0,0,0]}}}], "range": [0, len(text)]}]}
    mats["texts"].append({"id": mid, "type": "subtitle", "content": json.dumps(co, ensure_ascii=False)})
    return mid

def build_draft(req: BuildRequest):
    """Core build function - chạy trong thread riêng"""
    global _build_status
    _build_status = {"running": True, "done": False, "error": None, "result": None}
    try:
        footage = Path(req.footage_folder)
        voice   = footage / req.voice_file
        bgm     = footage / req.bgm_file if req.bgm_file else None
        draft_dir = CAPCUT_DRAFTS / req.project_name

        log_push(f"📁 Footage: {footage}", "info", 0, 6)
        log_push(f"🎙️  Voice: {voice.name} | exists={voice.exists()}", "info", 0, 6)
        if bgm: log_push(f"🎵 BGM: {bgm.name} | exists={bgm.exists()}", "info", 0, 6)

        # ── BƯỚC 1: Beat detection ────────────────────────────────────────
        log_push("🔊 [1/6] Phân tích beat BGM...", "info", 1, 6)
        beats_us = []
        bpm = 120.0
        if bgm and bgm.exists():
            try:
                import autoedit_engine
                beat_res = autoedit_engine.detect_audio_beats(str(bgm))
                beats_us = beat_res.get("beats_us", [])
                bpm = beat_res.get("bpm", 120)
                log_push(f"   BPM: {bpm:.1f} | {len(beats_us)} beats", "success", 1, 6)
            except Exception as e:
                log_push(f"   ⚠️ Beat detection lỗi: {e}", "warn", 1, 6)

        # ── BƯỚC 2: IDs & Folder ─────────────────────────────────────────
        log_push("🔑 [2/6] Tạo IDs và folder structure...", "info", 2, 6)
        DRAFT_ID    = uuidv4()
        PROJECT_ID  = uuidv4()
        TIMELINE_ID = uuidv4()
        log_push(f"   DRAFT_ID: {DRAFT_ID}", "info", 2, 6)

        if draft_dir.exists(): shutil.rmtree(draft_dir)
        draft_dir.mkdir(parents=True)
        for sd in ["adjust_mask","common_attachment","matting","qr_upload","Resources","smart_crop","subdraft"]:
            src = REF_DIR / sd; dst = draft_dir / sd
            shutil.copytree(src, dst) if src.is_dir() else dst.mkdir(parents=True)
        for rf in ["attachment_pc_common.json","draft.extra","draft_agency_config.json","draft_biz_config.json","draft_settings","key_value.json","performance_opt_info.json","timeline_layout.json","draft_cover.jpg"]:
            if (REF_DIR / rf).exists(): shutil.copy2(REF_DIR / rf, draft_dir / rf)
        TL_DIR = draft_dir / "Timelines" / TIMELINE_ID
        TL_DIR.mkdir(parents=True); (TL_DIR/"attachment").mkdir(); (TL_DIR/"common_attachment").mkdir()
        ref_tl = [d for d in (REF_DIR/"Timelines").iterdir() if d.is_dir() and not d.name.startswith('.')] if (REF_DIR/"Timelines").exists() else []
        if ref_tl:
            for tf in ["draft.extra","attachment_pc_common.json","draft_cover.jpg"]:
                if (ref_tl[0]/tf).exists(): shutil.copy2(ref_tl[0]/tf, TL_DIR/tf)
        now_us = int(time.time() * 1_000_000)
        proj_data = {"config":{"color_space":-1,"hdr_vivid":False,"mixed_track_mode_on":False,"render_index_track_mode_on":False,"use_float_render":False},"create_time":now_us,"id":PROJECT_ID,"main_timeline_id":TIMELINE_ID,"timelines":[{"create_time":now_us,"id":TIMELINE_ID,"is_marked_delete":False,"name":"Dòng thời gian 01","update_time":now_us}],"update_time":now_us,"version":0}
        for fn in ["project.json","project.json.bak"]:
            with open(draft_dir/"Timelines"/fn,"w",encoding="utf-8") as f: json.dump(proj_data,f)
        log_push("   ✓ Folder structure OK", "success", 2, 6)

        # ── BƯỚC 3: Build Materials & Tracks ─────────────────────────────
        log_push(f"🎞️  [3/6] Build {len(req.scenes)} phân cảnh...", "info", 3, 6)
        mats = {"videos":[],"audios":[],"texts":[],"speeds":[],"canvases":[],"beats":[],"material_animations":[],"video_effects":[],"transitions":[]}

        # Audio mats
        vm = uuidv4(); vp = str(voice).replace("\\","/")
        mats["audios"].append({"id":vm,"type":"audio","path":vp,"media_path":vp,"duration":3_600_000_000,"material_name":voice.name})
        bm = None
        if bgm and bgm.exists():
            bm = uuidv4(); bp2 = str(bgm).replace("\\","/")
            mats["audios"].append({"id":bm,"type":"audio","path":bp2,"media_path":bp2,"duration":3_600_000_000,"material_name":bgm.name})
        beat_m = uuidv4()
        mats["beats"].append({"id":beat_m,"type":"beats","enable_ai_beats":False,"gear":404,"gear_count":0,"mode":404,"user_beats":beats_us,"user_delete_ai_beats":None,"ai_beats":{"melody_url":"","melody_path":"","beats_url":"","beats_path":"","melody_percents":[0.0],"beat_speed_infos":[]}})

        tk_a   = {"id":uuidv4(),"type":"video","flag":0,"segments":[]}
        tk_b   = {"id":uuidv4(),"type":"video","flag":1,"segments":[]}
        tk_sub = {"id":uuidv4(),"type":"text","flag":1,"segments":[]}
        tk_hook= {"id":uuidv4(),"type":"text","flag":0,"segments":[]}
        tk_vo  = {"id":uuidv4(),"type":"audio","flag":0,"segments":[]}
        tk_bgm = {"id":uuidv4(),"type":"audio","flag":0,"segments":[]}

        # A-Roll base: lấy scene đầu tiên có aroll / hoặc dùng broll file 0
        aroll_path = None
        for sc in req.scenes:
            if sc.broll_file:
                aroll_path = footage / sc.broll_file  # fallback dùng B-Roll đầu làm A-Roll nếu không có Pocket riêng
                break
        if aroll_path and aroll_path.exists():
            am = uuidv4(); ap2 = str(aroll_path).replace("\\","/")
            mats["videos"].append({"id":am,"type":"video","path":ap2,"media_path":ap2,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":aroll_path.name})
        else:
            am = None

        broll_cache = {}; cur = 0; total_bytes = 0
        if voice.exists(): total_bytes += voice.stat().st_size
        if bgm and bgm.exists(): total_bytes += bgm.stat().st_size

        for i, sc in enumerate(req.scenes):
            dur   = int(round(sc.voice_dur * 1_000_000))
            vs_us = int(round(sc.voice_start * 1_000_000))
            as_us = int(round(sc.aroll_src * 1_000_000))

            # A-Roll segment
            if am:
                tk_a["segments"].append({"id":uuidv4(),"material_id":am,"extra_material_refs":[spd(mats),cvs(mats)],"source_timerange":{"start":as_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})

            # B-Roll overlay
            if sc.broll_file and sc.broll_dur > 0:
                bf = footage / sc.broll_file
                if bf.exists():
                    key = str(bf)
                    if key not in broll_cache:
                        bid = uuidv4(); bp3 = str(bf).replace("\\","/")
                        mats["videos"].append({"id":bid,"type":"video","path":bp3,"media_path":bp3,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":bf.name})
                        broll_cache[key] = bid; total_bytes += bf.stat().st_size
                    bd_us = int(round(sc.broll_delay * 1_000_000))
                    bd_dur = min(int(round(sc.broll_dur * 1_000_000)), dur - bd_us)
                    if bd_dur > 0:
                        tk_b["segments"].append({"id":uuidv4(),"material_id":broll_cache[key],"extra_material_refs":[spd(mats),cvs(mats)],"source_timerange":{"start":0,"duration":bd_dur},"target_timerange":{"start":cur+bd_us,"duration":bd_dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})

            # Voice
            tk_vo["segments"].append({"id":uuidv4(),"material_id":vm,"extra_material_refs":[spd(mats)],"source_timerange":{"start":vs_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"volume":2.8})

            # Subtitle
            sm = make_subtitle_mat(mats, sc.text)
            tk_sub["segments"].append({"id":uuidv4(),"material_id":sm,"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":0.77,"y":0.77},"transform":{"x":0.0,"y":-0.404}},"visible":True})

            broll_icon = "🎬" if sc.broll_file else "👤"
            log_push(f"   [{i+1:02d}/{len(req.scenes)}] {broll_icon} {sc.voice_dur}s → {sc.text[:40]}...", "info", 3, 6)
            cur += dur

        total_dur = cur

        # Hook banner
        if req.hook_text:
            hco = {"text":req.hook_text,"styles":[{"fill":{"content":{"render_type":"solid","solid":{"color":[1.0,0.88,0.18]}}},"font":{"path":FONT_BOLD,"id":""},"size":11.0,"bold":True,"shadows":[{"angle":-45,"thickness_projection_angle":-45,"thickness_projection_enable":False,"diffuse":0.025,"alpha":0.85,"distance":5.0,"content":{"render_type":"solid","solid":{"color":[0,0,0]}}}],"range":[0,len(req.hook_text)]}]}
            hm = uuidv4(); mats["texts"].append({"id":hm,"type":"text","content":json.dumps(hco,ensure_ascii=False)})
            tk_hook["segments"].append({"id":uuidv4(),"material_id":hm,"target_timerange":{"start":0,"duration":4_500_000},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.35}},"visible":True})

        # BGM
        if bm:
            tk_bgm["segments"].append({"id":uuidv4(),"material_id":bm,"extra_material_refs":[spd(mats),beat_m],"source_timerange":{"start":0,"duration":total_dur},"target_timerange":{"start":0,"duration":total_dur},"volume":0.25})

        log_push(f"   ✓ {total_dur/1e6:.1f}s | A:{len(tk_a['segments'])} B:{len(tk_b['segments'])} Sub:{len(tk_sub['segments'])}", "success", 3, 6)

        # ── BƯỚC 4: Write JSON files ───────────────────────────────────────
        log_push("💾 [4/6] Ghi draft_content.json...", "info", 4, 6)
        platform = {"os":"windows","os_version":"10.0.26300","app_id":359289,"app_version":"9.6.0","app_source":"cc","device_id":"612209cf1d1b1487af31c962c9ad8841","hard_disk_id":"","mac_address":"260094fa7ee4b1ee84ffeb93d5742c8f,2555f7cefd05f80d9c72db7c0673e6d2"}
        tracks_list = []
        if am: tracks_list.append(tk_a)
        if tk_b["segments"]: tracks_list.append(tk_b)
        tracks_list += [tk_vo, tk_bgm, tk_sub, tk_hook]
        dc = {"canvas_config":{"height":1920,"ratio":"original","width":1080},"color_space":-1,"config":{"adjust_max_index":1,"attachment_info":[],"combination_max_index":1,"export_range":None,"extract_audio_last_index":1,"hdr_vivid":False,"lyrics_recognition_id":"","lyrics_sync":True,"lyrics_taskinfo":[],"maintrack_adsorb":True,"material_save_mode":0,"multi_language_current":"none","multi_language_list":[],"multi_language_main":"none","multi_language_mode":"none","original_sound_last_index":1,"record_audio_last_index":1,"sticker_max_index":1,"subtitle_keywords_config":None,"subtitle_recognition_id":"","subtitle_sync":True,"subtitle_taskinfo":[],"system_font_list":[],"use_float_render":False,"video_mute":False,"voice_change_sync":False,"zoom_info_params":None},"cover":None,"create_time":0,"duration":total_dur,"extra_info":None,"fps":30.0,"free_render_index_mode_on":False,"function_assistant_info":{"fixed_rec_applied":False,"smart_rec_applied":False},"group_container":None,"id":TIMELINE_ID,"is_drop_frame_timecode":False,"keyframe_graph_list":[],"keyframes":{"adjusts":[],"audios":[],"effects":[],"filters":[],"handwrites":[],"stickers":[],"texts":[],"videos":[]},"last_modified_platform":platform,"lyrics_effects":[],"materials":mats,"mixed_track_mode_on":False,"mutable_config":None,"name":"","new_version":"189.0.0","path":"","platform":platform,"relationships":[],"render_index_track_mode_on":False,"retouch_cover":None,"smart_ads_info":None,"source":"default","static_cover_image_path":"","time_marks":None,"tracks":tracks_list,"uneven_animation_template_info":{"composition":""},"update_time":0,"version":360000}
        for td in [draft_dir, TL_DIR]:
            for fn in ["draft_content.json","template-2.tmp","draft_content.json.bak"]:
                with open(td/fn,"w",encoding="utf-8") as f: json.dump(dc,f,ensure_ascii=False)

        fold_win = str(draft_dir).replace("/","\\"); fold_fwd = str(draft_dir).replace("\\","/")
        meta = {"cloud_draft_cover":False,"cloud_draft_sync":False,"cloud_package_completed_time":"","draft_cloud_capcut_purchase_info":"","draft_cloud_last_action_download":False,"draft_cloud_package_type":"","draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":"draft_cover.jpg","draft_deeplink_url":"","draft_enterprise_info":{"draft_enterprise_extra":"","draft_enterprise_id":"","draft_enterprise_name":"","enterprise_material":[]},"draft_fold_path":fold_win,"draft_has_unfinished_aigc_video_effect":False,"draft_id":DRAFT_ID,"draft_is_ae_produce":False,"draft_is_ai_packaging_used":False,"draft_is_ai_shorts":False,"draft_is_ai_translate":False,"draft_is_article_video_draft":False,"draft_is_cloud_temp_draft":False,"draft_is_from_deeplink":"false","draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_materials":[{"type":0,"value":[]},{"type":1,"value":[]},{"type":2,"value":[]},{"type":3,"value":[]},{"type":6,"value":[]},{"type":7,"value":[]},{"type":8,"value":[]}],"draft_materials_copied_info":[],"draft_name":req.project_name,"draft_need_rename_folder":False,"draft_new_version":"","draft_removable_storage_device":"","draft_root_path":str(CAPCUT_DRAFTS).replace("/","\\"),"draft_segment_extra_info":[],"draft_timeline_materials_size_":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
        with open(draft_dir/"draft_meta_info.json","w",encoding="utf-8") as f: json.dump(meta,f,ensure_ascii=False)

        with open(CAPCUT_DRAFTS/"root_meta_info.json","r",encoding="utf-8") as f: root_data = json.load(f)
        entry = {"cloud_draft_cover":False,"cloud_draft_sync":False,"draft_cloud_last_action_download":False,"draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":fold_fwd+"/draft_cover.jpg","draft_fold_path":fold_fwd,"draft_id":DRAFT_ID,"draft_is_ai_shorts":False,"draft_is_cloud_temp_draft":False,"draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_json_file":fold_fwd+"/draft_content.json","draft_name":req.project_name,"draft_new_version":"","draft_root_path":str(CAPCUT_DRAFTS).replace("\\","/"),"draft_timeline_materials_size":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","streaming_edit_draft_ready":True,"tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
        store = root_data.get("all_draft_store",[])
        store = [x for x in store if x.get("draft_name") != req.project_name]
        store.insert(0, entry); root_data["all_draft_store"] = store
        with open(CAPCUT_DRAFTS/"root_meta_info.json","w",encoding="utf-8") as f: json.dump(root_data,f,ensure_ascii=False)
        log_push("   ✓ Đã đăng ký vào root_meta_info.json", "success", 4, 6)

        # ── BƯỚC 5: Launch + Auto-click ──────────────────────────────────
        if req.launch_capcut:
            log_push("🚀 [5/6] Launch CapCut + Auto-click timeline...", "info", 5, 6)
            try:
                import subprocess, ctypes, psutil, win32gui, win32process, win32con, win32api

                def find_cc():
                    res=[]
                    def cb(h,_):
                        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)=='CapCut':
                            try:
                                _,pid=win32process.GetWindowThreadProcessId(h)
                                if 'capcut' in psutil.Process(pid).name().lower():
                                    r=win32gui.GetWindowRect(h)
                                    if r[2]-r[0]>300: res.append(h)
                            except: pass
                    win32gui.EnumWindows(cb,None); return res

                def safe_front(hwnd):
                    u=ctypes.windll.user32
                    try: u.AllowSetForegroundWindow(-1)
                    except: pass
                    try:
                        if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
                        else: win32gui.ShowWindow(hwnd,win32con.SW_SHOW)
                    except: pass
                    try:
                        fg=u.GetForegroundWindow()
                        if fg:
                            ft,_=win32process.GetWindowThreadProcessId(fg)
                            ct=win32api.GetCurrentThreadId()
                            u.AttachThreadInput(ct,ft,True)
                            try: win32gui.BringWindowToTop(hwnd); win32gui.SetForegroundWindow(hwnd)
                            except: pass
                            u.AttachThreadInput(ct,ft,False)
                    except: pass
                    try:
                        win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST,0,0,0,0,win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
                        time.sleep(0.05)
                        win32gui.SetWindowPos(hwnd,win32con.HWND_NOTOPMOST,0,0,0,0,win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
                    except: pass

                cc_running = any('capcut' in p.name().lower() for p in psutil.process_iter(['name']))
                if not cc_running:
                    apps = Path(LOCALAPPDATA)/"CapCut"/"Apps"
                    exe = None
                    for d in sorted(apps.iterdir(),reverse=True) if apps.exists() else []:
                        c=d/"CapCut.exe"
                        if c.exists(): exe=c; break
                    if exe:
                        subprocess.Popen([str(exe)])
                        log_push(f"   CapCut đang khởi động...", "info", 5, 6)

                hwnd = None
                for _ in range(24):
                    time.sleep(0.5)
                    hwnds = find_cc()
                    if hwnds: hwnd = hwnds[0]; break

                if hwnd:
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2]-rect[0]; h = rect[3]-rect[1]
                    safe_front(hwnd)
                    time.sleep(2.5)
                    cx = rect[0]+int(w*0.160); cy = rect[1]+int(h*0.736)
                    u=ctypes.windll.user32; u.SetCursorPos(cx,cy); time.sleep(0.15)
                    for _ in range(2):
                        u.mouse_event(0x0002,0,0,0,0); time.sleep(0.05)
                        u.mouse_event(0x0004,0,0,0,0); time.sleep(0.08)
                    log_push(f"   ✓ Double-click tại ({cx},{cy}) → Timeline đang mở...", "success", 5, 6)
                else:
                    log_push("   ⚠️ Không tìm thấy cửa sổ CapCut", "warn", 5, 6)
            except Exception as e:
                log_push(f"   ⚠️ Launch error: {e}", "warn", 5, 6)

        log_push(f"✅ [6/6] HOÀN TẤT! {req.project_name} | {total_dur/1e6:.0f}s | {len(req.scenes)} cảnh", "success", 6, 6)
        _build_status = {"running": False, "done": True, "error": None, "result": {"project": req.project_name, "duration_s": total_dur/1e6, "scenes": len(req.scenes)}}

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        log_push(f"❌ LỖI: {e}", "error", 0, 6)
        _build_status = {"running": False, "done": True, "error": str(e), "result": None}

# ─── API ROUTES ───────────────────────────────────────────────────────────────

@app.get("/api/status")
async def status_stream():
    """SSE stream - push log realtime về browser"""
    async def generate():
        sent = 0
        while True:
            with _log_lock:
                new_logs = _log_queue[sent:]
                sent = len(_log_queue)
            for log in new_logs:
                yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
            if not _build_status["running"] and sent > 0 and not new_logs:
                yield f"data: {json.dumps({'done': True, 'result': _build_status['result'], 'error': _build_status['error']}, ensure_ascii=False)}\n\n"
                break
            await asyncio.sleep(0.15)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/build")
async def api_build(req: BuildRequest):
    global _log_queue
    if _build_status["running"]:
        raise HTTPException(409, "Build đang chạy, vui lòng chờ...")
    with _log_lock:
        _log_queue = []
    t = threading.Thread(target=build_draft, args=(req,), daemon=True)
    t.start()
    return {"ok": True, "message": "Build đã bắt đầu, theo dõi qua /api/status"}

@app.post("/api/scan")
async def api_scan(req: ScanRequest):
    """Quét folder và trả về danh sách file footage"""
    p = Path(req.folder_path)
    if not p.exists():
        raise HTTPException(404, f"Folder không tồn tại: {req.folder_path}")
    video_exts = {".mp4",".mov",".avi",".mkv",".mts",".m2ts",".m4v"}
    audio_exts = {".wav",".mp3",".aac",".m4a",".flac"}
    videos, audios = [], []
    for f in sorted(p.iterdir()):
        if f.is_file():
            ext = f.suffix.lower()
            size_mb = f.stat().st_size // 1024 // 1024
            info = {"name": f.name, "size_mb": size_mb, "path": str(f)}
            if ext in video_exts: videos.append(info)
            elif ext in audio_exts: audios.append(info)
    return {"folder": str(p), "videos": videos, "audios": audios, "total": len(videos)+len(audios)}

@app.get("/api/build_status")
async def build_status_poll():
    return JSONResponse(_build_status)

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(BASE_DIR / "static" / "script_editor.html", encoding="utf-8") as f:
        return f.read()

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    print("🌐 AI Script Editor → http://localhost:7788")
    uvicorn.run(app, host="0.0.0.0", port=7788, log_level="warning")
