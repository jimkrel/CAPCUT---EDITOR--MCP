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
    
    # Tao cover hop le (khong bao gio tao file 0 byte lam crash CapCut)
    cover_path = os.path.join(proj_dir, 'draft_cover.jpg')
    if not os.path.exists(cover_path) or os.path.getsize(cover_path) == 0:
        found_sample = False
        for entry in os.scandir(root_dir):
            if entry.is_dir() and entry.name != project_name:
                sample_cov = os.path.join(entry.path, 'draft_cover.jpg')
                if os.path.exists(sample_cov) and os.path.getsize(sample_cov) > 1000:
                    import shutil
                    try:
                        shutil.copyfile(sample_cov, cover_path)
                        found_sample = True
                        break
                    except Exception:
                        pass
        if not found_sample:
            valid_jpg = (
                b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05'
                b'\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c'
                b' $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4'
                b'\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05'
                b'\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
            )
            try:
                with open(cover_path, 'wb') as f:
                    f.write(valid_jpg)
            except Exception:
                pass

    # Tao draft_meta_info.json trong thu muc du an
    proj_meta_path = os.path.join(proj_dir, 'draft_meta_info.json')
    proj_meta = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "cloud_package_completed_time": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_package_type": "",
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "draft_cover.jpg",
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": []
        },
        "draft_fold_path": proj_dir.replace('\\', '/'),
        "draft_has_unfinished_aigc_video_effect": False,
        "draft_id": draft_id,
        "draft_is_ae_produce": False,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_materials": [
            {"type": 0, "value": []},
            {"type": 1, "value": []},
            {"type": 2, "value": []},
            {"type": 3, "value": []},
            {"type": 6, "value": []},
            {"type": 7, "value": []},
            {"type": 8, "value": []}
        ],
        "draft_materials_copied_info": [],
        "draft_name": project_name,
        "draft_need_rename_folder": False,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_root_path": root_dir, # Native Windows backslashes
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": 0,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "pippit_avatar_url": "",
        "pippit_extra_info": "",
        "pippit_id": "",
        "pippit_user_name": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration
    }
    with open(proj_meta_path, 'w', encoding='utf-8') as f:
        json.dump(proj_meta, f, ensure_ascii=False)

    # Dang ky vao all_draft_store cua root_meta_info.json
    proj_dir_norm = proj_dir.replace('\\', '/')
    root_entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": f"{proj_dir_norm}\\draft_cover.jpg",
        "draft_fold_path": proj_dir_norm,
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": f"{proj_dir_norm}\\draft_content.json",
        "draft_name": project_name,
        "draft_new_version": "",
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
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
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
