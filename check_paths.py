import json
from pathlib import Path

kb23_dir = Path(r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\BBSM_SET3_KB23')
content = json.load(open(kb23_dir / 'draft_content.json', encoding='utf-8'))

print('=== AUDIOS IN DRAFT_CONTENT ===')
for a in content['materials']['audios']:
    p = a.get('path', '')
    exists = Path(p).exists() if p else False
    print(f"Audio ID: {a.get('id')}, Name: {a.get('material_name')}, Exists: {exists}")
    print(f"  Path: {p}")

print('\n=== VIDEOS IN DRAFT_CONTENT ===')
for v in content['materials']['videos']:
    p = v.get('path', '')
    exists = Path(p).exists() if p else False
    print(f"Video ID: {v.get('id')}, Name: {v.get('material_name')}, Exists: {exists}")
    print(f"  Path: {p}")

print('\n=== FONTS ===')
for t in content['materials']['texts'][:2]:
    c = json.loads(t.get('content', '{}'))
    for s in c.get('styles', []):
        fp = s.get('font', {}).get('path', '')
        print(f"Font path: {fp}, Exists: {Path(fp).exists() if fp else False}")
