"""
KB23_FULL_AUTO.PY - Build + Launch + Auto-Open Timeline trong CapCut
=====================================================================
Script này làm tất cả trong 1 lần chạy:
  1. Build draft KB23 (A-Roll/B-Roll hybrid)
  2. Đăng ký vào root_meta_info.json
  3. Launch CapCut Desktop
  4. Auto-click mở timeline KB23

Dùng như video @pedrorojas.ec: AI điều khiển video editor
"""
import os, sys, time, json, shutil, uuid, subprocess, ctypes, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("kb23_auto")

BASE_DIR = Path(r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio")
sys.path.insert(0, str(BASE_DIR))
import autoedit_engine

def uuidv4(): return str(uuid.uuid4()).upper()

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PROJECT_NAME    = "BBSM_SET3_KB23"
LOCALAPPDATA    = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS   = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
DRAFT_DIR       = CAPCUT_DRAFTS / PROJECT_NAME
REF_DIR         = CAPCUT_DRAFTS / "1017"
FOOTAGE_DIR     = Path(r"D:\BAO_BI_SAC_MAU_FOOTAGE\KB23")
VOICE_WAV       = FOOTAGE_DIR / "vj_voice_kb23.wav"
BGM_PATH        = FOOTAGE_DIR / "bgm_funky_upbeat.mp3"
WIN_FONTS       = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts"
FONT_BOLD       = str(WIN_FONTS / "Montserrat-Bold.otf").replace("\\", "/") if (WIN_FONTS / "Montserrat-Bold.otf").exists() else ""

# ─── BƯỚC 1: BUILD DRAFT ─────────────────────────────────────────────────────
log.info("=" * 60)
log.info("BƯỚC 1: Build draft BBSM_SET3_KB23 (A-Roll/B-Roll Hybrid)")
log.info("=" * 60)

beat_res = autoedit_engine.detect_audio_beats(str(BGM_PATH))
beats_us = beat_res.get("beats_us", [])
bpm      = beat_res.get("bpm", 120)
log.info(f"BGM BPM: {bpm:.1f} | Beats: {len(beats_us)}")

# Kịch bản 10 phân cảnh
scenes = [
    {"text": "Anh/chị bán đồ ăn mang đi, muốn tìm tô đựng gọn gàng, in được logo quán",
     "voice_start": 7.0, "voice_dur": 4.0,
     "aroll_src": 0.0, "broll": None, "broll_delay": 0.0, "broll_dur": 0.0},
    {"text": "Thì có thể tham khảo mẫu tô kraft này, đây cũng là mẫu tô thông dụng đang được nhiều anh chị lựa chọn tại BBSM nha",
     "voice_start": 11.0, "voice_dur": 5.0,
     "aroll_src": 4.0, "broll": "C1721.MP4", "broll_delay": 1.5, "broll_dur": 3.5},
    {"text": "Loại này có 2 size chính là 750ml và 1000ml",
     "voice_start": 17.0, "voice_dur": 4.0,
     "aroll_src": 9.0, "broll": "C1751.MP4", "broll_delay": 0.5, "broll_dur": 3.5},
    {"text": "Phù hợp cho các món như: mì cay, mì trộn, bún nước tương, salad hay nhiều món ăn nhanh khác",
     "voice_start": 21.0, "voice_dur": 4.0,
     "aroll_src": 13.0, "broll": "C1781.MP4", "broll_delay": 0.3, "broll_dur": 3.7},
    {"text": "Có thể đựng cả đồ khô và đồ nước luôn nha anh/chị",
     "voice_start": 25.0, "voice_dur": 3.0,
     "aroll_src": 17.0, "broll": "C1821.MP4", "broll_delay": 1.0, "broll_dur": 2.0},
    {"text": "Với chất liệu kraft mang lại cảm giác mộc mạc, nhìn sạch sẽ và chỉn chu khi đóng gói cho khách mang đi",
     "voice_start": 31.0, "voice_dur": 6.0,
     "aroll_src": 20.0, "broll": "C1861.MP4", "broll_delay": 1.5, "broll_dur": 4.0},
    {"text": "Có thể sử dụng nắp PET trong veo với các món đồ lạnh và nắp PP dẻo dai cho món nóng, tuỳ thuộc vào nhu cầu của quán",
     "voice_start": 46.0, "voice_dur": 8.0,
     "aroll_src": 26.0, "broll": "C1901.MP4", "broll_delay": 1.8, "broll_dur": 5.0},
    {"text": "Đặc biệt, tô kraft này có thể in logo 1 màu, cho quán nào muốn tạo độ nhận diện",
     "voice_start": 58.0, "voice_dur": 5.0,
     "aroll_src": 34.0, "broll": "C1951.MP4", "broll_delay": 1.0, "broll_dur": 4.0},
    {"text": "Giúp chiếc tô trông vừa mắt, chuyên nghiệp hơn hẳn",
     "voice_start": 64.0, "voice_dur": 3.0,
     "aroll_src": 39.0, "broll": "C2001.MP4", "broll_delay": 0.5, "broll_dur": 2.5},
    {"text": "Nếu quán mình đang cần mẫu tô kraft tiện lợi, dễ dùng như thế này, thì nhắn ngay BBSM để được hỗ trợ và tư vấn chi tiết hơn nha",
     "voice_start": 68.0, "voice_dur": 8.0,
     "aroll_src": 42.0, "broll": "C2036.MP4", "broll_delay": 3.0, "broll_dur": 5.0},
]

# IDs
DRAFT_ID    = uuidv4()
PROJECT_ID  = uuidv4()
TIMELINE_ID = uuidv4()
log.info(f"DRAFT_ID: {DRAFT_ID}")

# Folder setup
if DRAFT_DIR.exists(): shutil.rmtree(DRAFT_DIR)
DRAFT_DIR.mkdir(parents=True)
for sd in ["adjust_mask","common_attachment","matting","qr_upload","Resources","smart_crop","subdraft"]:
    src = REF_DIR / sd
    dst = DRAFT_DIR / sd
    shutil.copytree(src, dst) if src.is_dir() else dst.mkdir(parents=True)
for rf in ["attachment_pc_common.json","draft.extra","draft_agency_config.json","draft_biz_config.json","draft_settings","key_value.json","performance_opt_info.json","timeline_layout.json","draft_cover.jpg"]:
    if (REF_DIR / rf).exists(): shutil.copy2(REF_DIR / rf, DRAFT_DIR / rf)

TL_DIR = DRAFT_DIR / "Timelines" / TIMELINE_ID
TL_DIR.mkdir(parents=True)
(TL_DIR / "attachment").mkdir()
(TL_DIR / "common_attachment").mkdir()

# Copy timeline support files
ref_tl_ids = [d for d in (REF_DIR/"Timelines").iterdir() if d.is_dir() and not d.name.startswith('.')] if (REF_DIR/"Timelines").exists() else []
if ref_tl_ids:
    for tf in ["draft.extra","attachment_editing.json","attachment_pc_common.json","draft_cover.jpg"]:
        if (ref_tl_ids[0]/tf).exists(): shutil.copy2(ref_tl_ids[0]/tf, TL_DIR/tf)

now_us = int(time.time() * 1_000_000)

# project.json
proj_data = {"config":{"color_space":-1,"hdr_vivid":False,"mixed_track_mode_on":False,"render_index_track_mode_on":False,"use_float_render":False},"create_time":now_us,"id":PROJECT_ID,"main_timeline_id":TIMELINE_ID,"timelines":[{"create_time":now_us,"id":TIMELINE_ID,"is_marked_delete":False,"name":"Dòng thời gian 01","update_time":now_us}],"update_time":now_us,"version":0}
for fn in ["project.json","project.json.bak"]:
    with open(DRAFT_DIR/"Timelines"/fn,"w",encoding="utf-8") as f: json.dump(proj_data,f)

# Materials & tracks
mats = {"videos":[],"audios":[],"texts":[],"speeds":[],"canvases":[],"beats":[],"material_animations":[],"video_effects":[],"transitions":[]}
def spd(v=1.0):
    sid=uuidv4(); mats["speeds"].append({"id":sid,"mode":0,"speed":float(v),"type":"speed"}); return sid
def cvs():
    cid=uuidv4(); mats["canvases"].append({"id":cid,"type":"canvas_color","color":"#00000000"}); return cid

# Audio mats
v_mid=uuidv4(); vp=str(VOICE_WAV).replace("\\","/")
mats["audios"].append({"id":v_mid,"type":"audio","path":vp,"media_path":vp,"duration":3_600_000_000,"material_name":VOICE_WAV.name})
b_mid=uuidv4(); bp=str(BGM_PATH).replace("\\","/")
mats["audios"].append({"id":b_mid,"type":"audio","path":bp,"media_path":bp,"duration":3_600_000_000,"material_name":BGM_PATH.name})
beat_mid=uuidv4()
mats["beats"].append({"id":beat_mid,"type":"beats","enable_ai_beats":False,"gear":404,"gear_count":0,"mode":404,"user_beats":beats_us,"user_delete_ai_beats":None,"ai_beats":{"melody_url":"","melody_path":"","beats_url":"","beats_path":"","melody_percents":[0.0],"beat_speed_infos":[]}})

# Tracks
tk_a={"id":uuidv4(),"type":"video","flag":0,"segments":[]}  # A-Roll
tk_b={"id":uuidv4(),"type":"video","flag":1,"segments":[]}  # B-Roll overlay
tk_sub={"id":uuidv4(),"type":"text","flag":1,"segments":[]}  # Subtitles
tk_hook={"id":uuidv4(),"type":"text","flag":0,"segments":[]}  # Hook
tk_vo={"id":uuidv4(),"type":"audio","flag":0,"segments":[]}  # Voice
tk_bgm={"id":uuidv4(),"type":"audio","flag":0,"segments":[]}  # BGM

# Register A-Roll material (C1701 - dùng chung cho toàn bộ A-Roll)
aroll_path = FOOTAGE_DIR/"C1701.MP4"
am_id=uuidv4(); ap=str(aroll_path).replace("\\","/")
mats["videos"].append({"id":am_id,"type":"video","path":ap,"media_path":ap,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":"C1701.MP4"})

broll_cache={}
cur=0; total_bytes=0
for f in [VOICE_WAV,BGM_PATH,aroll_path]:
    if f.exists(): total_bytes+=f.stat().st_size

for sc in scenes:
    dur    = int(round(sc["voice_dur"]*1_000_000))
    vs_us  = int(round(sc["voice_start"]*1_000_000))
    as_us  = int(round(sc["aroll_src"]*1_000_000))

    # A-Roll segment
    tk_a["segments"].append({"id":uuidv4(),"material_id":am_id,"extra_material_refs":[spd(),cvs()],"source_timerange":{"start":as_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})

    # B-Roll overlay
    if sc["broll"] and sc["broll_dur"] > 0:
        broll_file = FOOTAGE_DIR / sc["broll"]
        if broll_file.exists():
            key=str(broll_file)
            if key not in broll_cache:
                bm=uuidv4(); bp2=str(broll_file).replace("\\","/")
                mats["videos"].append({"id":bm,"type":"video","path":bp2,"media_path":bp2,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":broll_file.name})
                broll_cache[key]=bm
                total_bytes+=broll_file.stat().st_size
            bd_us=int(round(sc["broll_delay"]*1_000_000))
            bd_dur=min(int(round(sc["broll_dur"]*1_000_000)), dur-bd_us)
            if bd_dur>0:
                tk_b["segments"].append({"id":uuidv4(),"material_id":broll_cache[key],"extra_material_refs":[spd(),cvs()],"source_timerange":{"start":0,"duration":bd_dur},"target_timerange":{"start":cur+bd_us,"duration":bd_dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})

    # Voice
    tk_vo["segments"].append({"id":uuidv4(),"material_id":v_mid,"extra_material_refs":[spd()],"source_timerange":{"start":vs_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"volume":2.8})

    # Subtitle
    txt=sc["text"]
    co={"text":txt,"styles":[{"fill":{"content":{"render_type":"solid","solid":{"color":[1,1,1]}}},"font":{"path":FONT_BOLD,"id":""},"size":9.5,"bold":True,"shadows":[{"angle":-45,"thickness_projection_angle":-45,"thickness_projection_enable":False,"diffuse":0.025,"alpha":0.72,"distance":5.0,"content":{"render_type":"solid","solid":{"color":[0,0,0]}}}],"range":[0,len(txt)]}]}
    sm=uuidv4(); mats["texts"].append({"id":sm,"type":"subtitle","content":json.dumps(co,ensure_ascii=False)})
    tk_sub["segments"].append({"id":uuidv4(),"material_id":sm,"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":0.77,"y":0.77},"transform":{"x":0.0,"y":-0.404}},"visible":True})

    cur+=dur

total_dur=cur

# Hook banner
ht="TÔ KRAFT ĐỰNG ĐỒ ĂN MANG ĐI"
hco={"text":ht,"styles":[{"fill":{"content":{"render_type":"solid","solid":{"color":[1.0,0.88,0.18]}}},"font":{"path":FONT_BOLD,"id":""},"size":11.0,"bold":True,"shadows":[{"angle":-45,"thickness_projection_angle":-45,"thickness_projection_enable":False,"diffuse":0.025,"alpha":0.85,"distance":5.0,"content":{"render_type":"solid","solid":{"color":[0,0,0]}}}],"range":[0,len(ht)]}]}
hm=uuidv4(); mats["texts"].append({"id":hm,"type":"text","content":json.dumps(hco,ensure_ascii=False)})
tk_hook["segments"].append({"id":uuidv4(),"material_id":hm,"target_timerange":{"start":0,"duration":4_500_000},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.35}},"visible":True})

# BGM
tk_bgm["segments"].append({"id":uuidv4(),"material_id":b_mid,"extra_material_refs":[spd(),beat_mid],"source_timerange":{"start":0,"duration":total_dur},"target_timerange":{"start":0,"duration":total_dur},"volume":0.25})

platform={"os":"windows","os_version":"10.0.26300","app_id":359289,"app_version":"9.6.0","app_source":"cc","device_id":"612209cf1d1b1487af31c962c9ad8841","hard_disk_id":"","mac_address":"260094fa7ee4b1ee84ffeb93d5742c8f,2555f7cefd05f80d9c72db7c0673e6d2"}
dc={"canvas_config":{"height":1920,"ratio":"original","width":1080},"color_space":-1,"config":{"adjust_max_index":1,"attachment_info":[],"combination_max_index":1,"export_range":None,"extract_audio_last_index":1,"hdr_vivid":False,"lyrics_recognition_id":"","lyrics_sync":True,"lyrics_taskinfo":[],"maintrack_adsorb":True,"material_save_mode":0,"multi_language_current":"none","multi_language_list":[],"multi_language_main":"none","multi_language_mode":"none","original_sound_last_index":1,"record_audio_last_index":1,"sticker_max_index":1,"subtitle_keywords_config":None,"subtitle_recognition_id":"","subtitle_sync":True,"subtitle_taskinfo":[],"system_font_list":[],"use_float_render":False,"video_mute":False,"voice_change_sync":False,"zoom_info_params":None},"cover":None,"create_time":0,"duration":total_dur,"extra_info":None,"fps":30.0,"free_render_index_mode_on":False,"function_assistant_info":{"fixed_rec_applied":False,"smart_rec_applied":False},"group_container":None,"id":TIMELINE_ID,"is_drop_frame_timecode":False,"keyframe_graph_list":[],"keyframes":{"adjusts":[],"audios":[],"effects":[],"filters":[],"handwrites":[],"stickers":[],"texts":[],"videos":[]},"last_modified_platform":platform,"lyrics_effects":[],"materials":mats,"mixed_track_mode_on":False,"mutable_config":None,"name":"","new_version":"189.0.0","path":"","platform":platform,"relationships":[],"render_index_track_mode_on":False,"retouch_cover":None,"smart_ads_info":None,"source":"default","static_cover_image_path":"","time_marks":None,"tracks":[tk_a,tk_b,tk_vo,tk_bgm,tk_sub,tk_hook],"uneven_animation_template_info":{"composition":""},"update_time":0,"version":360000}

for td in [DRAFT_DIR, TL_DIR]:
    for fn in ["draft_content.json","template-2.tmp","draft_content.json.bak"]:
        with open(td/fn,"w",encoding="utf-8") as f: json.dump(dc,f,ensure_ascii=False)

log.info(f"✓ Draft built: {total_dur/1e6:.1f}s | A-Roll:{len(tk_a['segments'])} | B-Roll:{len(tk_b['segments'])} | Sub:{len(tk_sub['segments'])}")

# draft_meta_info
fold_win=str(DRAFT_DIR).replace("/","\\")
meta={"cloud_draft_cover":False,"cloud_draft_sync":False,"cloud_package_completed_time":"","draft_cloud_capcut_purchase_info":"","draft_cloud_last_action_download":False,"draft_cloud_package_type":"","draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":"draft_cover.jpg","draft_deeplink_url":"","draft_enterprise_info":{"draft_enterprise_extra":"","draft_enterprise_id":"","draft_enterprise_name":"","enterprise_material":[]},"draft_fold_path":fold_win,"draft_has_unfinished_aigc_video_effect":False,"draft_id":DRAFT_ID,"draft_is_ae_produce":False,"draft_is_ai_packaging_used":False,"draft_is_ai_shorts":False,"draft_is_ai_translate":False,"draft_is_article_video_draft":False,"draft_is_cloud_temp_draft":False,"draft_is_from_deeplink":"false","draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_materials":[{"type":0,"value":[]},{"type":1,"value":[]},{"type":2,"value":[]},{"type":3,"value":[]},{"type":6,"value":[]},{"type":7,"value":[]},{"type":8,"value":[]}],"draft_materials_copied_info":[],"draft_name":PROJECT_NAME,"draft_need_rename_folder":False,"draft_new_version":"","draft_removable_storage_device":"","draft_root_path":str(CAPCUT_DRAFTS).replace("/","\\"),"draft_segment_extra_info":[],"draft_timeline_materials_size_":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
with open(DRAFT_DIR/"draft_meta_info.json","w",encoding="utf-8") as f: json.dump(meta,f,ensure_ascii=False)

# root_meta_info
with open(CAPCUT_DRAFTS/"root_meta_info.json","r",encoding="utf-8") as f: root=json.load(f)
fold_fwd=str(DRAFT_DIR).replace("\\","/")
entry={"cloud_draft_cover":False,"cloud_draft_sync":False,"draft_cloud_last_action_download":False,"draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":fold_fwd+"/draft_cover.jpg","draft_fold_path":fold_fwd,"draft_id":DRAFT_ID,"draft_is_ai_shorts":False,"draft_is_cloud_temp_draft":False,"draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_json_file":fold_fwd+"/draft_content.json","draft_name":PROJECT_NAME,"draft_new_version":"","draft_root_path":str(CAPCUT_DRAFTS).replace("\\","/"),"draft_timeline_materials_size":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","streaming_edit_draft_ready":True,"tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
store=root.get("all_draft_store",[])
store=[x for x in store if x.get("draft_name")!=PROJECT_NAME]
store.insert(0,entry)
root["all_draft_store"]=store
with open(CAPCUT_DRAFTS/"root_meta_info.json","w",encoding="utf-8") as f: json.dump(root,f,ensure_ascii=False)
log.info("✓ Đã đăng ký vào root_meta_info.json vị trí 0")

# ─── BƯỚC 2: LAUNCH CAPCUT ───────────────────────────────────────────────────
log.info("=" * 60)
log.info("BƯỚC 2: Launch CapCut Desktop")
log.info("=" * 60)

import psutil, win32gui, win32process, win32con, win32api

def is_capcut_running():
    for p in psutil.process_iter(['name']):
        try:
            if 'capcut' in (p.info.get('name') or '').lower():
                return True
        except: pass
    return False

def find_capcut_hwnd():
    result=[]
    def cb(hwnd,_):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd)=='CapCut':
            _,pid=win32process.GetWindowThreadProcessId(hwnd)
            try:
                name=psutil.Process(pid).name().lower()
                if 'capcut' in name:
                    r=win32gui.GetWindowRect(hwnd)
                    if r[2]-r[0]>300 and r[3]-r[1]>200:
                        result.append(hwnd)
            except: pass
    win32gui.EnumWindows(cb,None)
    return result

def bring_front(hwnd):
    u = ctypes.windll.user32
    # Cho phep bat ky process set foreground
    try: u.AllowSetForegroundWindow(-1)
    except: pass
    # Restore neu minimized
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    except: pass
    # AttachThreadInput trick
    try:
        fg = u.GetForegroundWindow()
        if fg and fg != hwnd:
            ft, _ = win32process.GetWindowThreadProcessId(fg)
            ct = win32api.GetCurrentThreadId()
            u.AttachThreadInput(ct, ft, True)
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            except: pass
            u.AttachThreadInput(ct, ft, False)
        else:
            try: win32gui.SetForegroundWindow(hwnd)
            except: pass
    except: pass
    # Fallback: dung SetWindowPos TOPMOST roi tra ve NOTOPMOST
    try:
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0,0,0,0,
            win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0,0,0,0,
            win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
    except: pass

# Launch nếu chưa chạy
if not is_capcut_running():
    capcut_apps = Path(LOCALAPPDATA)/"CapCut"/"Apps"
    exe = None
    if capcut_apps.exists():
        for d in sorted(capcut_apps.iterdir(),reverse=True):
            c=d/"CapCut.exe"
            if c.exists(): exe=c; break
        if not exe:
            flat=capcut_apps/"CapCut.exe"
            if flat.exists(): exe=flat
    if exe:
        log.info(f"Launching: {exe}")
        subprocess.Popen([str(exe)], shell=False)
    else:
        log.error("Không tìm thấy CapCut.exe!")
        sys.exit(1)
else:
    log.info("CapCut đã chạy, đang focus...")

# Chờ CapCut mở
log.info("Đang chờ CapCut khởi động (tối đa 15s)...")
hwnd = None
for _ in range(30):
    time.sleep(0.5)
    hwnds = find_capcut_hwnd()
    if hwnds:
        hwnd = hwnds[0]
        bring_front(hwnd)
        log.info(f"✓ CapCut window found: HWND={hwnd}")
        break

if not hwnd:
    log.warning("Không tìm thấy cửa sổ CapCut. Hãy mở thủ công và chọn BBSM_SET3_KB23")
    sys.exit(0)

# ─── BƯỚC 3: AUTO-CLICK MỞ PROJECT ──────────────────────────────────────────
log.info("=" * 60)
log.info("BƯỚC 3: Auto-click mở project BBSM_SET3_KB23")
log.info("=" * 60)

# Chờ trang chủ CapCut load xong
log.info("Chờ UI CapCut load (3s)...")
time.sleep(3.0)
bring_front(hwnd)
time.sleep(0.5)

rect = win32gui.GetWindowRect(hwnd)
left, top, right, bottom = rect
w = right - left
h = bottom - top
log.info(f"CapCut window: {w}x{h} at ({left},{top})")

# Project card đầu tiên: khoảng 16% width, 73% height của cửa sổ
# (dựa theo phân tích ảnh chụp màn hình CapCut 1920x1080)
click_x = left + int(w * 0.160)
click_y = top  + int(h * 0.736)
log.info(f"Click tại ({click_x}, {click_y}) - Project card #1")

u = ctypes.windll.user32
u.SetCursorPos(click_x, click_y)
time.sleep(0.15)

# Double-click
for _ in range(2):
    u.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.05)
    u.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    time.sleep(0.08)

log.info("✓ Double-click sent!")
time.sleep(2.0)

# Đưa cửa sổ lên foreground sau khi timeline load
hwnds2 = find_capcut_hwnd()
if hwnds2:
    bring_front(hwnds2[0])

log.info("=" * 60)
log.info(f"🎉 HOÀN TẤT! BBSM_SET3_KB23 đã được mở trong CapCut Timeline")
log.info(f"   Thời lượng: {total_dur/1e6:.1f}s")
log.info(f"   Tracks: A-Roll({len(tk_a['segments'])}) + B-Roll({len(tk_b['segments'])}) + Voice + BGM + Sub + Hook")
log.info("=" * 60)
