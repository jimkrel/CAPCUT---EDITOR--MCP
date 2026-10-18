import json
from pathlib import Path

p = Path(r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\BBSM_SET3_KB23\draft_content.json')
c = json.load(open(p, encoding='utf-8'))

all_ok = True
print('Audios:')
for a in c['materials']['audios']:
    pt = a['path']
    ex = Path(pt).exists()
    has_bad = '\uf022' in pt
    print(f"  {a['id']}: {pt} | Exists: {ex} | Bad char: {has_bad}")
    if not ex or has_bad:
        all_ok = False

print('\nVideos:')
for v in c['materials']['videos']:
    pt = v['path']
    ex = Path(pt).exists()
    has_bad = '\uf022' in pt
    print(f"  {v['id']}: {pt} | Exists: {ex} | Bad char: {has_bad}")
    if not ex or has_bad:
        all_ok = False

print('\nTexts:')
for t in c['materials']['texts']:
    co = json.loads(t['content'])
    print(f"  Text: {co['text'][:35]}...")

print('\nTracks count:', len(c['tracks']))
for i, tr in enumerate(c['tracks']):
    print(f"  Track {i} ({tr['type']}): {len(tr['segments'])} segments")

print('\n' + ('=== VERIFICATION PASSED 100% ===' if all_ok else '=== VERIFICATION FAILED ==='))
