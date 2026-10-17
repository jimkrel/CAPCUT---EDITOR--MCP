import json
import os

path = r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\BBSM_SET3_21\draft_content.json'
with open(path, encoding='utf-8') as f:
    d = json.load(f)

print('TOTAL TRACKS:', len(d.get('tracks', [])))
for i, t in enumerate(d.get('tracks', [])):
    t_type = t.get('type')
    t_flag = t.get('flag')
    segs = t.get('segments', [])
    print(f"Track #{i:02d} | type={t_type:<8} | flag={t_flag} | seg_count={len(segs):<2}")
    for s_idx, s in enumerate(segs[:2]):
        tr = s.get('target_timerange') or {}
        st = tr.get('start', 0) / 1e6
        dur = tr.get('duration', 0) / 1e6
        mid = s.get('material_id', '')[:8]
        vol = s.get('volume', 1.0)
        speed = s.get('speed', 1.0)
        clip = s.get('clip') or {}
        scale = clip.get('scale', {}).get('x', 1.0) if clip else 1.0
        extra = s.get('extra_material_refs') or []
        trans = s.get('transition') or {}
        print(f"   [{s_idx}] {st:5.2f}s -> {st+dur:5.2f}s ({dur:4.2f}s) | mid={mid} | scale={scale:.2f} | vol={vol} | speed={speed} | trans={bool(trans)} | refs={len(extra)}")

print('\nMATERIALS SUMMARY:')
mats = d.get('materials', {})
for k, v in mats.items():
    if isinstance(v, list) and len(v) > 0:
        print(f"  {k:<25}: {len(v)}")

# Check transition structure
transitions = mats.get('transitions', [])
print('\nTRANSITIONS EXAMPLE:')
for tr in transitions[:2]:
    print(" ", tr)

# Check video_effects structure
effects = mats.get('video_effects', [])
print('\nVIDEO EFFECTS EXAMPLE:')
for eff in effects[:2]:
    print(" ", eff.get('name'), eff.get('effect_id'), eff.get('id'))
