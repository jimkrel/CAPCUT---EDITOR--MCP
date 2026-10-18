import json
from pathlib import Path
import re

draft_dir = Path(r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft')

count = 0
for d in sorted(draft_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
    if d.is_dir() and (d / 'draft_content.json').exists():
        content_path = d / 'draft_content.json'
        try:
            with open(content_path, 'r', encoding='utf-8') as f:
                c = json.load(f)
            placeholders = set(re.findall(r'##_draftpath_placeholder_[a-zA-Z0-9\-]+_##', json.dumps(c)))
            print(f'=== {d.name} ===')
            print(f'  name: "{c.get("name")}"')
            print(f'  id: {c.get("id")}')
            print(f'  static_cover_image_path: {c.get("static_cover_image_path")}')
            print(f'  placeholders: {placeholders}')
            # Check draft_meta_info.json
            meta_path = d / 'draft_meta_info.json'
            if meta_path.exists():
                with open(meta_path, 'r', encoding='utf-8') as mf:
                    m = json.load(mf)
                print(f'  meta draft_id: {m.get("draft_id")}')
                print(f'  meta draft_fold_path: {m.get("draft_fold_path")}')
                print(f'  meta draft_name: {m.get("draft_name")}')
            count += 1
            if count >= 6:
                break
        except Exception as e:
            print(f'Error reading {d.name}: {e}')
