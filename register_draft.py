import json
import os
import time
import uuid
import sys

def register_project_in_capcut(project_name: str):
    root_dir = os.path.expanduser('~/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft')
    root_meta_path = os.path.join(root_dir, 'root_meta_info.json')
    if not os.path.exists(root_meta_path):
        return {"ok": False, "error": f"root_meta_info.json not found at {root_meta_path}"}
    
    with open(root_meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
        
    proj_dir = os.path.join(root_dir, project_name)
    draft_json = os.path.join(proj_dir, 'draft_content.json')
    if not os.path.exists(draft_json):
        return {"ok": False, "error": f"draft_content.json not found in {proj_dir}"}
        
    with open(draft_json, 'r', encoding='utf-8') as f:
        d = json.load(f)
        
    now_us = int(time.time() * 1_000_000)
    draft_id = d.get('id', str(uuid.uuid4())).upper()
    duration = d.get('duration', 0)
    
    # Tao cover gia neu chua co
    cover_path = os.path.join(proj_dir, 'draft_cover.jpg')
    if not os.path.exists(cover_path):
        try:
            with open(cover_path, 'wb') as f:
                f.write(b'')
        except Exception:
            pass

    # Tao draft_meta_info.json trong thu muc du an
    proj_meta_path = os.path.join(proj_dir, 'draft_meta_info.json')
    proj_meta = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": True,
        "draft_cover": "draft_cover.jpg",
        "draft_fold_path": proj_dir.replace('\\', '/'),
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": draft_json.replace('\\', '/'),
        "draft_name": project_name,
        "draft_new_version": "164.0.0",
        "draft_root_path": root_dir.replace('\\', '/'),
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration
    }
    with open(proj_meta_path, 'w', encoding='utf-8') as f:
        json.dump(proj_meta, f, ensure_ascii=False, indent=2)

    # Dang ky vao all_draft_store cua root_meta_info.json
    root_entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": True,
        "draft_cloud_purchase_info": "{\n}\n",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "{\n}\n",
        "draft_cloud_videocut_purchase_info": "{\"template_type\":\"\",\"unlock_type\":\"\"}",
        "draft_cover": cover_path.replace('\\', '/'),
        "draft_fold_path": proj_dir.replace('\\', '/'),
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": draft_json.replace('\\', '/'),
        "draft_name": project_name,
        "draft_new_version": "164.0.0",
        "draft_root_path": root_dir.replace('\\', '/'),
        "draft_timeline_materials_size": 0,
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
        "tm_duration": duration
    }

    store = meta.get('all_draft_store', [])
    store = [x for x in store if x.get('draft_name') != project_name]
    store.insert(0, root_entry)
    meta['all_draft_store'] = store

    with open(root_meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"ok": True, "message": f"Registered '{project_name}' into CapCut root_meta_info.json"}

if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'TEST_REALTIME_VERIFY'
    res = register_project_in_capcut(name)
    print(res)
