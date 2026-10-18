import json
import pathlib

p = pathlib.Path(r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\BBSM_SET3_KB23\draft_content.json')
d = json.load(open(p, encoding='utf-8'))
print('id:', d.get('id'))
print('name:', d.get('name'))
print('duration:', d.get('duration'))
print('tracks:', len(d.get('tracks', [])))
for i, t in enumerate(d.get('tracks', [])):
    print(f"  track {i} ({t.get('type')}): {len(t.get('segments', []))} segments")
print('materials audios:', len(d.get('materials', {}).get('audios', [])))
for a in d.get('materials', {}).get('audios', []):
    print('  audio:', a.get('path'))
print('materials videos:', len(d.get('materials', {}).get('videos', [])))
for v in d.get('materials', {}).get('videos', []):
    print('  video:', v.get('path'))
