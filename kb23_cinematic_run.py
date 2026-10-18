"""
KB23_CINEMATIC_RUN.PY - Chạy song song như video @pedrorojas.ec
================================================================
Layout:
  [Terminal script (trái 50%)] | [CapCut (phải 50%)]

Thứ tự:
  1. Mở CapCut + sắp xếp cửa sổ song song
  2. Build draft KB23 (output realtime trong terminal)
  3. Auto-click mở project trong CapCut ngay khi xong
"""
import os, sys, subprocess, ctypes, time, json, shutil, uuid, win32gui, win32process, win32con, win32api
from pathlib import Path
import psutil

BASE_DIR = Path(r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio")
sys.path.insert(0, str(BASE_DIR))
import autoedit_engine

def uuidv4(): return str(uuid.uuid4()).upper()

# ─── BƯỚC 0: SẮP XẾP CỬA SỔ SONG SONG ──────────────────────────────────────
user32 = ctypes.windll.user32
SW = user32.GetSystemMetrics(0)   # Screen Width
SH = user32.GetSystemMetrics(1)   # Screen Height

def find_hwnd_by_pid(pid):
    result = []
    def cb(h, _):
        try:
            _, p = win32process.GetWindowThreadProcessId(h)
            if p == pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
                r = win32gui.GetWindowRect(h)
                if r[2]-r[0] > 100:
                    result.append(h)
        except: pass
    win32gui.EnumWindows(cb, None)
    return result

def find_capcut_hwnd():
    result = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == 'CapCut':
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
                if 'capcut' in psutil.Process(pid).name().lower():
                    r = win32gui.GetWindowRect(h)
                    if r[2]-r[0] > 300: result.append(h)
            except: pass
    win32gui.EnumWindows(cb, None)
    return result

def set_window_pos(hwnd, x, y, w, h):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
    except: pass

def safe_foreground(hwnd):
    try: user32.AllowSetForegroundWindow(-1)
    except: pass
    try:
        fg = user32.GetForegroundWindow()
        if fg:
            ft,_ = win32process.GetWindowThreadProcessId(fg)
            ct = win32api.GetCurrentThreadId()
            user32.AttachThreadInput(ct, ft, True)
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            except: pass
            user32.AttachThreadInput(ct, ft, False)
    except: pass
    try:
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0,0,0,0,
            win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0,0,0,0,
            win32con.SWP_NOMOVE|win32con.SWP_NOSIZE|win32con.SWP_SHOWWINDOW)
    except: pass

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DRAFTS = Path(LOCALAPPDATA) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"

# ── Launch CapCut ở BÊN PHẢI màn hình ──
capcut_running = any('capcut' in p.name().lower() for p in psutil.process_iter(['name']))
if not capcut_running:
    print("🚀 Launching CapCut bên phải màn hình...")
    capcut_apps = Path(LOCALAPPDATA) / "CapCut" / "Apps"
    exe = None
    for d in sorted(capcut_apps.iterdir(), reverse=True) if capcut_apps.exists() else []:
        c = d / "CapCut.exe"
        if c.exists(): exe = c; break
    if not exe:
        flat = capcut_apps / "CapCut.exe"
        if flat.exists(): exe = flat
    if exe:
        subprocess.Popen([str(exe)])
        print(f"   CapCut.exe launched, chờ cửa sổ xuất hiện...")

# ── Lấy terminal window hiện tại (Windows Terminal / cmd / powershell) ──
cur_pid = os.getpid()
parent_pid = psutil.Process(cur_pid).ppid()
term_hwnd = None
for pid_try in [parent_pid, psutil.Process(parent_pid).ppid() if parent_pid else None]:
    if pid_try:
        hwnds = find_hwnd_by_pid(pid_try)
        if hwnds: term_hwnd = hwnds[0]; break

# ── Chờ CapCut mở (tối đa 12s) ──
print("⏳ Chờ CapCut khởi động...")
capcut_hwnd = None
for _ in range(24):
    time.sleep(0.5)
    hwnds = find_capcut_hwnd()
    if hwnds: capcut_hwnd = hwnds[0]; break

half_w = SW // 2

if term_hwnd:
    print(f"📐 Sắp xếp Terminal (trái) + CapCut (phải) - {SW}x{SH}")
    # Terminal bên trái
    set_window_pos(term_hwnd, 0, 0, half_w, SH)

if capcut_hwnd:
    # CapCut bên phải
    set_window_pos(capcut_hwnd, half_w, 0, half_w, SH)
    safe_foreground(capcut_hwnd)
    time.sleep(0.3)

# Kéo terminal lên foreground để thấy output
if term_hwnd:
    safe_foreground(term_hwnd)
    time.sleep(0.2)

print()
print("=" * 55)
print("  🎬 AI ĐANG BUILD DRAFT KB23 - XEM SONG SONG VỚI CAPCUT")
print("=" * 55)

# ─── BƯỚC 1: BUILD DRAFT ─────────────────────────────────────────────────────
FOOTAGE_DIR = Path(r"D:\BAO_BI_SAC_MAU_FOOTAGE\KB23")
VOICE_WAV   = FOOTAGE_DIR / "vj_voice_kb23.wav"
BGM_PATH    = FOOTAGE_DIR / "bgm_funky_upbeat.mp3"
DRAFT_DIR   = CAPCUT_DRAFTS / "BBSM_SET3_KB23"
REF_DIR     = CAPCUT_DRAFTS / "1017"
WIN_FONTS   = Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Fonts"
FONT_BOLD   = str(WIN_FONTS/"Montserrat-Bold.otf").replace("\\","/") if (WIN_FONTS/"Montserrat-Bold.otf").exists() else ""

print("\n[1/6] 🎵 Phân tích beat BGM...")
beat_res = autoedit_engine.detect_audio_beats(str(BGM_PATH))
beats_us = beat_res.get("beats_us", [])
bpm      = beat_res.get("bpm", 120)
print(f"      BPM: {bpm:.1f} | {len(beats_us)} beats detected")

print("\n[2/6] 📋 Generating unique IDs...")
DRAFT_ID    = uuidv4()
PROJECT_ID  = uuidv4()
TIMELINE_ID = uuidv4()
print(f"      DRAFT_ID:    {DRAFT_ID}")
print(f"      TIMELINE_ID: {TIMELINE_ID}")

print("\n[3/6] 📁 Thiết lập folder structure...")
if DRAFT_DIR.exists(): shutil.rmtree(DRAFT_DIR)
DRAFT_DIR.mkdir(parents=True)
for sd in ["adjust_mask","common_attachment","matting","qr_upload","Resources","smart_crop","subdraft"]:
    src=REF_DIR/sd; dst=DRAFT_DIR/sd
    shutil.copytree(src,dst) if src.is_dir() else dst.mkdir(parents=True)
for rf in ["attachment_pc_common.json","draft.extra","draft_agency_config.json","draft_biz_config.json","draft_settings","key_value.json","performance_opt_info.json","timeline_layout.json","draft_cover.jpg"]:
    if (REF_DIR/rf).exists(): shutil.copy2(REF_DIR/rf, DRAFT_DIR/rf)
TL_DIR = DRAFT_DIR/"Timelines"/TIMELINE_ID
TL_DIR.mkdir(parents=True)
(TL_DIR/"attachment").mkdir(); (TL_DIR/"common_attachment").mkdir()
ref_tl_ids=[d for d in (REF_DIR/"Timelines").iterdir() if d.is_dir() and not d.name.startswith('.')] if (REF_DIR/"Timelines").exists() else []
if ref_tl_ids:
    for tf in ["draft.extra","attachment_editing.json","attachment_pc_common.json","draft_cover.jpg"]:
        if (ref_tl_ids[0]/tf).exists(): shutil.copy2(ref_tl_ids[0]/tf, TL_DIR/tf)
now_us=int(time.time()*1_000_000)
proj_data={"config":{"color_space":-1,"hdr_vivid":False,"mixed_track_mode_on":False,"render_index_track_mode_on":False,"use_float_render":False},"create_time":now_us,"id":PROJECT_ID,"main_timeline_id":TIMELINE_ID,"timelines":[{"create_time":now_us,"id":TIMELINE_ID,"is_marked_delete":False,"name":"Dòng thời gian 01","update_time":now_us}],"update_time":now_us,"version":0}
for fn in ["project.json","project.json.bak"]:
    with open(DRAFT_DIR/"Timelines"/fn,"w",encoding="utf-8") as f: json.dump(proj_data,f)
print("      ✓ Folders OK")

print("\n[4/6] 🎞️  Build tracks (A-Roll + B-Roll + Audio + Subtitle)...")
scenes=[
    {"text":"Anh/chị bán đồ ăn mang đi, muốn tìm tô đựng gọn gàng, in được logo quán",         "vs":7.0,"vd":4.0,"as":0.0,"br":None,         "bd":0.0,"bdd":0.0},
    {"text":"Thì có thể tham khảo mẫu tô kraft này, đây cũng là mẫu tô thông dụng đang được nhiều anh chị lựa chọn tại BBSM nha","vs":11.0,"vd":5.0,"as":4.0,"br":"C1721.MP4","bd":1.5,"bdd":3.5},
    {"text":"Loại này có 2 size chính là 750ml và 1000ml",                                        "vs":17.0,"vd":4.0,"as":9.0,"br":"C1751.MP4","bd":0.5,"bdd":3.5},
    {"text":"Phù hợp cho các món như: mì cay, mì trộn, bún nước tương, salad hay nhiều món ăn nhanh khác","vs":21.0,"vd":4.0,"as":13.0,"br":"C1781.MP4","bd":0.3,"bdd":3.7},
    {"text":"Có thể đựng cả đồ khô và đồ nước luôn nha anh/chị",                                 "vs":25.0,"vd":3.0,"as":17.0,"br":"C1821.MP4","bd":1.0,"bdd":2.0},
    {"text":"Với chất liệu kraft mang lại cảm giác mộc mạc, nhìn sạch sẽ và chỉn chu khi đóng gói cho khách mang đi","vs":31.0,"vd":6.0,"as":20.0,"br":"C1861.MP4","bd":1.5,"bdd":4.0},
    {"text":"Có thể sử dụng nắp PET trong veo với các món đồ lạnh và nắp PP dẻo dai cho món nóng, tuỳ thuộc vào nhu cầu của quán","vs":46.0,"vd":8.0,"as":26.0,"br":"C1901.MP4","bd":1.8,"bdd":5.0},
    {"text":"Đặc biệt, tô kraft này có thể in logo 1 màu, cho quán nào muốn tạo độ nhận diện",  "vs":58.0,"vd":5.0,"as":34.0,"br":"C1951.MP4","bd":1.0,"bdd":4.0},
    {"text":"Giúp chiếc tô trông vừa mắt, chuyên nghiệp hơn hẳn",                               "vs":64.0,"vd":3.0,"as":39.0,"br":"C2001.MP4","bd":0.5,"bdd":2.5},
    {"text":"Nếu quán mình đang cần mẫu tô kraft tiện lợi, dễ dùng như thế này, thì nhắn ngay BBSM để được hỗ trợ và tư vấn chi tiết hơn nha","vs":68.0,"vd":8.0,"as":42.0,"br":"C2036.MP4","bd":3.0,"bdd":5.0},
]

mats={"videos":[],"audios":[],"texts":[],"speeds":[],"canvases":[],"beats":[],"material_animations":[],"video_effects":[],"transitions":[]}
def spd(v=1.0):
    sid=uuidv4(); mats["speeds"].append({"id":sid,"mode":0,"speed":float(v),"type":"speed"}); return sid
def cvs():
    cid=uuidv4(); mats["canvases"].append({"id":cid,"type":"canvas_color","color":"#00000000"}); return cid

vm=uuidv4(); vp=str(VOICE_WAV).replace("\\","/")
mats["audios"].append({"id":vm,"type":"audio","path":vp,"media_path":vp,"duration":3_600_000_000,"material_name":VOICE_WAV.name})
bm=uuidv4(); bp_str=str(BGM_PATH).replace("\\","/")
mats["audios"].append({"id":bm,"type":"audio","path":bp_str,"media_path":bp_str,"duration":3_600_000_000,"material_name":BGM_PATH.name})
beat_m=uuidv4()
mats["beats"].append({"id":beat_m,"type":"beats","enable_ai_beats":False,"gear":404,"gear_count":0,"mode":404,"user_beats":beats_us,"user_delete_ai_beats":None,"ai_beats":{"melody_url":"","melody_path":"","beats_url":"","beats_path":"","melody_percents":[0.0],"beat_speed_infos":[]}})

tk_a={"id":uuidv4(),"type":"video","flag":0,"segments":[]}
tk_b={"id":uuidv4(),"type":"video","flag":1,"segments":[]}
tk_sub={"id":uuidv4(),"type":"text","flag":1,"segments":[]}
tk_hook={"id":uuidv4(),"type":"text","flag":0,"segments":[]}
tk_vo={"id":uuidv4(),"type":"audio","flag":0,"segments":[]}
tk_bgm={"id":uuidv4(),"type":"audio","flag":0,"segments":[]}

ap_str=str(FOOTAGE_DIR/"C1701.MP4").replace("\\","/")
am=uuidv4(); mats["videos"].append({"id":am,"type":"video","path":ap_str,"media_path":ap_str,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":"C1701.MP4"})

broll_cache={}; cur=0; total_bytes=0
for f in [VOICE_WAV,BGM_PATH,FOOTAGE_DIR/"C1701.MP4"]:
    if f.exists(): total_bytes+=f.stat().st_size

TRACK_LABELS=["A-Roll","B-Roll","Voice","Sub","Sub","Sub","Sub","Sub","Sub","Sub"]
for i, sc in enumerate(scenes):
    dur=int(round(sc["vd"]*1_000_000)); vs_us=int(round(sc["vs"]*1_000_000)); as_us=int(round(sc["as"]*1_000_000))
    # A-Roll
    tk_a["segments"].append({"id":uuidv4(),"material_id":am,"extra_material_refs":[spd(),cvs()],"source_timerange":{"start":as_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})
    # B-Roll
    if sc["br"] and sc["bdd"]>0:
        bf=FOOTAGE_DIR/sc["br"]
        if bf.exists():
            key=str(bf)
            if key not in broll_cache:
                bid=uuidv4(); bp2=str(bf).replace("\\","/")
                mats["videos"].append({"id":bid,"type":"video","path":bp2,"media_path":bp2,"width":3840,"height":2160,"duration":3_600_000_000,"has_audio":False,"material_name":bf.name})
                broll_cache[key]=bid; total_bytes+=bf.stat().st_size
            bd_us=int(round(sc["bd"]*1_000_000)); bd_dur=min(int(round(sc["bdd"]*1_000_000)),dur-bd_us)
            if bd_dur>0:
                tk_b["segments"].append({"id":uuidv4(),"material_id":broll_cache[key],"extra_material_refs":[spd(),cvs()],"source_timerange":{"start":0,"duration":bd_dur},"target_timerange":{"start":cur+bd_us,"duration":bd_dur},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.0}},"volume":0.0,"visible":True})
    # Voice
    tk_vo["segments"].append({"id":uuidv4(),"material_id":vm,"extra_material_refs":[spd()],"source_timerange":{"start":vs_us,"duration":dur},"target_timerange":{"start":cur,"duration":dur},"volume":2.8})
    # Subtitle
    txt=sc["text"]; co={"text":txt,"styles":[{"fill":{"content":{"render_type":"solid","solid":{"color":[1,1,1]}}},"font":{"path":FONT_BOLD,"id":""},"size":9.5,"bold":True,"shadows":[{"angle":-45,"thickness_projection_angle":-45,"thickness_projection_enable":False,"diffuse":0.025,"alpha":0.72,"distance":5.0,"content":{"render_type":"solid","solid":{"color":[0,0,0]}}}],"range":[0,len(txt)]}]}
    sm=uuidv4(); mats["texts"].append({"id":sm,"type":"subtitle","content":json.dumps(co,ensure_ascii=False)})
    tk_sub["segments"].append({"id":uuidv4(),"material_id":sm,"target_timerange":{"start":cur,"duration":dur},"clip":{"scale":{"x":0.77,"y":0.77},"transform":{"x":0.0,"y":-0.404}},"visible":True})

    broll_icon="🎬" if sc["br"] else "👤"
    print(f"      [{i+1:02d}/10] {broll_icon} {sc['vd']}s | voice@{sc['vs']}s {'+B-Roll('+sc['br']+')' if sc['br'] else '(A-Roll only)'}")
    cur+=dur

total_dur=cur
# Hook
ht="TÔ KRAFT ĐỰNG ĐỒ ĂN MANG ĐI"; hco={"text":ht,"styles":[{"fill":{"content":{"render_type":"solid","solid":{"color":[1.0,0.88,0.18]}}},"font":{"path":FONT_BOLD,"id":""},"size":11.0,"bold":True,"shadows":[{"angle":-45,"thickness_projection_angle":-45,"thickness_projection_enable":False,"diffuse":0.025,"alpha":0.85,"distance":5.0,"content":{"render_type":"solid","solid":{"color":[0,0,0]}}}],"range":[0,len(ht)]}]}
hm=uuidv4(); mats["texts"].append({"id":hm,"type":"text","content":json.dumps(hco,ensure_ascii=False)})
tk_hook["segments"].append({"id":uuidv4(),"material_id":hm,"target_timerange":{"start":0,"duration":4_500_000},"clip":{"scale":{"x":1.0,"y":1.0},"transform":{"x":0.0,"y":0.35}},"visible":True})
tk_bgm["segments"].append({"id":uuidv4(),"material_id":bm,"extra_material_refs":[spd(),beat_m],"source_timerange":{"start":0,"duration":total_dur},"target_timerange":{"start":0,"duration":total_dur},"volume":0.25})

print(f"\n      ✓ Timeline: {total_dur/1e6:.0f}s | A:{len(tk_a['segments'])} B:{len(tk_b['segments'])} Sub:{len(tk_sub['segments'])}")

print("\n[5/6] 💾 Ghi file draft (JSON → CapCut)...")
platform={"os":"windows","os_version":"10.0.26300","app_id":359289,"app_version":"9.6.0","app_source":"cc","device_id":"612209cf1d1b1487af31c962c9ad8841","hard_disk_id":"","mac_address":"260094fa7ee4b1ee84ffeb93d5742c8f,2555f7cefd05f80d9c72db7c0673e6d2"}
dc={"canvas_config":{"height":1920,"ratio":"original","width":1080},"color_space":-1,"config":{"adjust_max_index":1,"attachment_info":[],"combination_max_index":1,"export_range":None,"extract_audio_last_index":1,"hdr_vivid":False,"lyrics_recognition_id":"","lyrics_sync":True,"lyrics_taskinfo":[],"maintrack_adsorb":True,"material_save_mode":0,"multi_language_current":"none","multi_language_list":[],"multi_language_main":"none","multi_language_mode":"none","original_sound_last_index":1,"record_audio_last_index":1,"sticker_max_index":1,"subtitle_keywords_config":None,"subtitle_recognition_id":"","subtitle_sync":True,"subtitle_taskinfo":[],"system_font_list":[],"use_float_render":False,"video_mute":False,"voice_change_sync":False,"zoom_info_params":None},"cover":None,"create_time":0,"duration":total_dur,"extra_info":None,"fps":30.0,"free_render_index_mode_on":False,"function_assistant_info":{"fixed_rec_applied":False,"smart_rec_applied":False},"group_container":None,"id":TIMELINE_ID,"is_drop_frame_timecode":False,"keyframe_graph_list":[],"keyframes":{"adjusts":[],"audios":[],"effects":[],"filters":[],"handwrites":[],"stickers":[],"texts":[],"videos":[]},"last_modified_platform":platform,"lyrics_effects":[],"materials":mats,"mixed_track_mode_on":False,"mutable_config":None,"name":"","new_version":"189.0.0","path":"","platform":platform,"relationships":[],"render_index_track_mode_on":False,"retouch_cover":None,"smart_ads_info":None,"source":"default","static_cover_image_path":"","time_marks":None,"tracks":[tk_a,tk_b,tk_vo,tk_bgm,tk_sub,tk_hook],"uneven_animation_template_info":{"composition":""},"update_time":0,"version":360000}
for td in [DRAFT_DIR,TL_DIR]:
    for fn in ["draft_content.json","template-2.tmp","draft_content.json.bak"]:
        with open(td/fn,"w",encoding="utf-8") as f: json.dump(dc,f,ensure_ascii=False)
fold_win=str(DRAFT_DIR).replace("/","\\"); fold_fwd=str(DRAFT_DIR).replace("\\","/")
meta={"cloud_draft_cover":False,"cloud_draft_sync":False,"cloud_package_completed_time":"","draft_cloud_capcut_purchase_info":"","draft_cloud_last_action_download":False,"draft_cloud_package_type":"","draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":"draft_cover.jpg","draft_deeplink_url":"","draft_enterprise_info":{"draft_enterprise_extra":"","draft_enterprise_id":"","draft_enterprise_name":"","enterprise_material":[]},"draft_fold_path":fold_win,"draft_has_unfinished_aigc_video_effect":False,"draft_id":DRAFT_ID,"draft_is_ae_produce":False,"draft_is_ai_packaging_used":False,"draft_is_ai_shorts":False,"draft_is_ai_translate":False,"draft_is_article_video_draft":False,"draft_is_cloud_temp_draft":False,"draft_is_from_deeplink":"false","draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_materials":[{"type":0,"value":[]},{"type":1,"value":[]},{"type":2,"value":[]},{"type":3,"value":[]},{"type":6,"value":[]},{"type":7,"value":[]},{"type":8,"value":[]}],"draft_materials_copied_info":[],"draft_name":"BBSM_SET3_KB23","draft_need_rename_folder":False,"draft_new_version":"","draft_removable_storage_device":"","draft_root_path":str(CAPCUT_DRAFTS).replace("/","\\"),"draft_segment_extra_info":[],"draft_timeline_materials_size_":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
with open(DRAFT_DIR/"draft_meta_info.json","w",encoding="utf-8") as f: json.dump(meta,f,ensure_ascii=False)
with open(CAPCUT_DRAFTS/"root_meta_info.json","r",encoding="utf-8") as f: root=json.load(f)
entry={"cloud_draft_cover":False,"cloud_draft_sync":False,"draft_cloud_last_action_download":False,"draft_cloud_purchase_info":"","draft_cloud_template_id":"","draft_cloud_tutorial_info":"","draft_cloud_videocut_purchase_info":"","draft_cover":fold_fwd+"/draft_cover.jpg","draft_fold_path":fold_fwd,"draft_id":DRAFT_ID,"draft_is_ai_shorts":False,"draft_is_cloud_temp_draft":False,"draft_is_infinite_canvas_draft":False,"draft_is_invisible":False,"draft_is_pippit_draft":False,"draft_is_web_article_video":False,"draft_json_file":fold_fwd+"/draft_content.json","draft_name":"BBSM_SET3_KB23","draft_new_version":"","draft_root_path":str(CAPCUT_DRAFTS).replace("\\","/"),"draft_timeline_materials_size":total_bytes,"draft_type":"","draft_web_article_video_enter_from":"","pippit_avatar_url":"","pippit_extra_info":"","pippit_id":"","pippit_user_name":"","streaming_edit_draft_ready":True,"tm_draft_cloud_completed":"","tm_draft_cloud_entry_id":-1,"tm_draft_cloud_modified":0,"tm_draft_cloud_parent_entry_id":-1,"tm_draft_cloud_space_id":-1,"tm_draft_cloud_user_id":-1,"tm_draft_create":now_us,"tm_draft_modified":now_us,"tm_draft_removed":0,"tm_duration":total_dur}
store=root.get("all_draft_store",[]); store=[x for x in store if x.get("draft_name")!="BBSM_SET3_KB23"]; store.insert(0,entry); root["all_draft_store"]=store
with open(CAPCUT_DRAFTS/"root_meta_info.json","w",encoding="utf-8") as f: json.dump(root,f,ensure_ascii=False)
print("      ✓ draft_content.json + root_meta_info.json OK")

# ─── BƯỚC 2: AUTO-CLICK MỞ PROJECT TRONG CAPCUT ─────────────────────────────
print("\n[6/6] 🖱️  Auto-click mở BBSM_SET3_KB23 trong CapCut...")

capcut_hwnd = None
hwnds = find_capcut_hwnd()
if hwnds: capcut_hwnd = hwnds[0]

if not capcut_hwnd:
    print("      ⚠️  Chờ thêm CapCut (5s)...")
    for _ in range(10):
        time.sleep(0.5)
        hwnds = find_capcut_hwnd()
        if hwnds: capcut_hwnd = hwnds[0]; break

if capcut_hwnd:
    # Đưa CapCut bên phải lên foreground để click
    set_window_pos(capcut_hwnd, half_w, 0, half_w, SH)
    safe_foreground(capcut_hwnd)
    time.sleep(1.5)  # Chờ CapCut load trang chủ

    rect = win32gui.GetWindowRect(capcut_hwnd)
    left, top, right, bottom = rect
    w = right - left
    h = bottom - top
    click_x = left + int(w * 0.160)
    click_y = top  + int(h * 0.736)
    print(f"      CapCut: {w}x{h} | Click → ({click_x}, {click_y})")

    user32.SetCursorPos(click_x, click_y)
    time.sleep(0.15)
    for _ in range(2):
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.08)
    print("      ✓ Double-click sent → Đang mở timeline...")
    time.sleep(2.0)

    # Sau khi timeline load, đưa CapCut lên full right half
    hwnds2 = find_capcut_hwnd()
    if hwnds2: set_window_pos(hwnds2[0], half_w, 0, half_w, SH)

    # Terminal trái lại foreground
    if term_hwnd: safe_foreground(term_hwnd)
else:
    print("      ❌ Không tìm thấy CapCut - Hãy mở thủ công và chọn BBSM_SET3_KB23")

print()
print("=" * 55)
print("  ✅ DONE! BBSM_SET3_KB23 đã xuất hiện trong CapCut")
print(f"     {total_dur/1_000_000:.0f}s | 6 tracks | A-Roll+B-Roll hybrid")
print("=" * 55)
