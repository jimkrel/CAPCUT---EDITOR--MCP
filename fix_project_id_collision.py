import json
import os
import shutil
import uuid
from pathlib import Path

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
CAPCUT_DIR = Path(LOCALAPPDATA) / "CapCut"
DRAFTS_DIR = CAPCUT_DIR / "User Data" / "Projects" / "com.lveditor.draft"

PROJECT_NAME = "BBSM_SET3_KB23"
KB23_DIR = DRAFTS_DIR / PROJECT_NAME
KB20_DIR = DRAFTS_DIR / "BBSM_SET3_KB20"

# 1. Tạo unique UUID riêng biệt cho KB23 và KB20 (Chấm dứt trùng lặp DFB6AF57...)
KB23_ID = str(uuid.uuid4()).upper()
KB20_ID = str(uuid.uuid4()).upper()

print(f"🔑 Cấp phát Draft ID độc nhất vô nhị:")
print(f"  BBSM_SET3_KB23: {KB23_ID}")
print(f"  BBSM_SET3_KB20: {KB20_ID}")

# 2. Cập nhật BBSM_SET3_KB23
if KB23_DIR.exists():
    # 2.1 Cập nhật draft_content.json ở gốc
    root_content_file = KB23_DIR / "draft_content.json"
    content = json.load(open(root_content_file, encoding="utf-8"))
    content["id"] = KB23_ID
    content["name"] = PROJECT_NAME
    
    with open(root_content_file, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    with open(KB23_DIR / "template-2.tmp", "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    with open(KB23_DIR / "draft_content.json.bak", "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    # 2.2 Cập nhật cấu trúc Timelines
    tl_base = KB23_DIR / "Timelines"
    if tl_base.exists():
        # Xóa các thư mục timeline ID cũ
        for child in tl_base.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
        
        # Tạo thư mục timeline ID mới
        new_tl_dir = tl_base / KB23_ID
        new_tl_dir.mkdir(parents=True, exist_ok=True)
        
        with open(new_tl_dir / "draft_content.json", "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        with open(new_tl_dir / "template-2.tmp", "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        with open(new_tl_dir / "draft_content.json.bak", "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        # Cập nhật project.json trong Timelines
        pj = {
            "config": {
                "color_space": 0,
                "hdr_vivid": False,
                "mixed_track_mode_on": False,
                "render_index_track_mode_on": True,
                "use_float_render": True
            },
            "create_time": int(content.get("create_time", 1792337615) * 1_000_000),
            "id": KB23_ID,
            "main_timeline_id": KB23_ID,
            "timelines": [
                {
                    "create_time": int(content.get("create_time", 1792337615) * 1_000_000),
                    "id": KB23_ID,
                    "is_marked_delete": False,
                    "name": "Dòng thời gian 01",
                    "update_time": int(content.get("update_time", 1792337615) * 1_000_000)
                }
            ],
            "update_time": int(content.get("update_time", 1792337615) * 1_000_000),
            "version": 0
        }
        with open(tl_base / "project.json", "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=2)
        with open(tl_base / "project.json.bak", "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=2)

    kb23_dir_norm = str(KB23_DIR).replace("\\", "/")
    kb20_dir_norm = str(KB20_DIR).replace("\\", "/")

    # 2.3 Cập nhật draft_meta_info.json của KB23
    meta_file = KB23_DIR / "draft_meta_info.json"
    meta = json.load(open(meta_file, encoding="utf-8"))
    meta["draft_id"] = KB23_ID
    meta["draft_name"] = PROJECT_NAME
    meta["draft_fold_path"] = kb23_dir_norm
    meta["draft_root_path"] = str(DRAFTS_DIR).replace("\\", "/")
    meta["draft_json_file"] = f"{kb23_dir_norm}/draft_content.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

print("✓ Đã cập nhật toàn bộ metadata nội bộ của BBSM_SET3_KB23")

# 3. Cập nhật BBSM_SET3_KB20 để tách biệt hoàn toàn với BBSM_SET3_21_MASTER_CINEMATIC
if KB20_DIR.exists():
    meta20_file = KB20_DIR / "draft_meta_info.json"
    if meta20_file.exists():
        m20 = json.load(open(meta20_file, encoding="utf-8"))
        m20["draft_id"] = KB20_ID
        with open(meta20_file, "w", encoding="utf-8") as f:
            json.dump(m20, f, ensure_ascii=False, indent=2)
    c20_file = KB20_DIR / "draft_content.json"
    if c20_file.exists():
        c20 = json.load(open(c20_file, encoding="utf-8"))
        c20["id"] = KB20_ID
        with open(c20_file, "w", encoding="utf-8") as f:
            json.dump(c20, f, ensure_ascii=False, indent=2)
    print("✓ Đã gán ID độc lập cho BBSM_SET3_KB20")

# 4. Cập nhật User Data/Config/draftLayoutConfig.ini
layout_ini = CAPCUT_DIR / "User Data" / "Config" / "draftLayoutConfig.ini"
if layout_ini.exists():
    ini_txt = layout_ini.read_text(encoding="utf-8")
    if KB23_ID not in ini_txt:
        ini_txt += f"\n{KB23_ID}=4"
    if KB20_ID not in ini_txt:
        ini_txt += f"\n{KB20_ID}=4"
    layout_ini.write_text(ini_txt, encoding="utf-8")
    print("✓ Đã đăng ký layout timeline trong draftLayoutConfig.ini")

# 5. Cập nhật root_meta_info.json
root_meta_file = DRAFTS_DIR / "root_meta_info.json"
root_data = json.load(open(root_meta_file, encoding="utf-8"))
store = root_data.get("all_draft_store", [])

for item in store:
    if item.get("draft_name") == "BBSM_SET3_KB23":
        item["draft_id"] = KB23_ID
        item["draft_fold_path"] = kb23_dir_norm
        item["draft_json_file"] = f"{kb23_dir_norm}/draft_content.json"
        item["draft_cover"] = f"{kb23_dir_norm}/draft_cover.jpg"
    elif item.get("draft_name") == "BBSM_SET3_KB20":
        item["draft_id"] = KB20_ID
        item["draft_fold_path"] = kb20_dir_norm
        item["draft_json_file"] = f"{kb20_dir_norm}/draft_content.json"
        item["draft_cover"] = f"{kb20_dir_norm}/draft_cover.jpg"

# Đảm bảo BBSM_SET3_KB23 đứng ở vị trí số 0 đầu danh sách
kb23_item = next((x for x in store if x.get("draft_name") == "BBSM_SET3_KB23"), None)
if kb23_item:
    store = [x for x in store if x.get("draft_name") != "BBSM_SET3_KB23"]
    store.insert(0, kb23_item)

root_data["all_draft_store"] = store
with open(root_meta_file, "w", encoding="utf-8") as f:
    json.dump(root_data, f, ensure_ascii=False, indent=2)

print("✓ Đã cập nhật root_meta_info.json: BBSM_SET3_KB23 ở vị trí số 0 với ID độc nhất!")

# 6. Kiểm tra lại trùng lặp ID trên toàn hệ thống
from collections import Counter
counts = Counter(x["draft_id"] for x in root_data["all_draft_store"])
dups = {k: v for k, v in counts.items() if v > 1}
print(f"🔍 Kiểm tra trùng lặp ID còn lại: {len(dups)} (Nếu là 0 tức là 100% SẠCH)")
if dups:
    print(f"  Vẫn còn trùng: {dups}")
else:
    print("🎉 TUYỆT VỜI! Mọi dự án giờ đây đều có 1 Draft ID duy nhất, không còn bất kỳ xung đột đường dẫn nào!")
