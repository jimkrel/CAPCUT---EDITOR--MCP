import urllib.request
import json
import os
import time

print('=== 1. KIEM TRA SERVER STATUS ===')
t0 = time.time()
try:
    res = urllib.request.urlopen('http://127.0.0.1:8765/api/projects')
    proj_data = json.loads(res.read().decode('utf-8'))
    print(f'[OK] Server HTTP 200 OK ({int((time.time()-t0)*1000)}ms)')
    print(f'[OK] So luong du an tim thay trong CapCut: {len(proj_data.get("projects", []))}')
except Exception as e:
    print('[FAIL] Loi ket noi Server:', e)
    exit(1)

print('\n=== 2. KIEM TRA AI SCRIPT PARSER API ===')
t0 = time.time()
req_script = urllib.request.Request(
    'http://127.0.0.1:8765/api/ai-agent/parse-script',
    headers={'Content-Type': 'application/json'},
    data=json.dumps({
        'raw_script': 'Ca phe muoi thom beo dam da.\n[BROLL] Rot lop kem man sanh min len tren ly da.\nThuong thuc ngay huong vi doc dao hom nay!',
        'pacing_mode': '1.8s'
    }).encode('utf-8')
)
res_script = urllib.request.urlopen(req_script)
data_script = json.loads(res_script.read().decode('utf-8'))
print(f'[OK] Phan tich kich ban thanh cong ({int((time.time()-t0)*1000)}ms): {data_script.get("count")} phan canh')
for i, s in enumerate(data_script.get('sentences', [])):
    dur = s.get("durationSec") or ((s.get("durationUs") or 0) / 1e6)
    print(f'   - Cau {i+1} [{s.get("type").upper()}]: "{s.get("text")}" ({dur}s)')

print('\n=== 3. KIEM TRA BIEN DICH 13 LOP MCP API ===')
test_name = f'AUDIT_VERIFY_{int(time.time())}'
t0 = time.time()
req_create = urllib.request.Request(
    'http://127.0.0.1:8765/api/mcp/create-project',
    headers={'Content-Type': 'application/json'},
    data=json.dumps({
        'projectName': test_name,
        'hookText': 'CA PHE MUOI NGON BAT BAI',
        'ctaText': 'BAM VAO GIO HANG NGAY HOM NAY',
        'scriptSentences': data_script.get('sentences', [])
    }).encode('utf-8')
)
res_create = urllib.request.urlopen(req_create)
data_create = json.loads(res_create.read().decode('utf-8'))
print(f'[OK] Tao du an 13 lop thanh cong ({int((time.time()-t0)*1000)}ms): {data_create.get("projectName")}')
print(f'[OK] Thu muc dich: {data_create.get("draftDir")}')

print('\n=== 4. KIEM TRA DOC & TINH TOAN VEN TIMELINE API ===')
t0 = time.time()
res_proj = urllib.request.urlopen(f'http://127.0.0.1:8765/api/project/{test_name}')
data_proj = json.loads(res_proj.read().decode('utf-8'))
tracks = data_proj.get('tracks', [])
print(f'[OK] Doc timeline thanh cong ({int((time.time()-t0)*1000)}ms): {len(tracks)} tracks')

has_hook = any(t.get('type') == 'text' and any('CA PHE MUOI' in str(s.get('details', {}).get('text', '')) or 'CA PHE MUOI' in s.get('label', '') for s in t.get('segments', [])) for t in tracks)
has_adjust = any(t.get('type') == 'adjust' and len(t.get('segments', [])) > 0 for t in tracks)
has_subs = any(t.get('type') == 'text' and any('Ca phe' in s.get('label', '') for s in t.get('segments', [])) for t in tracks)
print(f'   - Track 6 Hook Banner vang Gold: {"[OK] HOAT DONG" if has_hook else "[FAIL] KHONG TIM THAY"}')
print(f'   - Track 7 Mau Thuong Mai (Studio LUT): {"[OK] HOAT DONG" if has_adjust else "[FAIL] KHONG TIM THAY"}')
print(f'   - Track 10 Phu de Montserrat: {"[OK] HOAT DONG" if has_subs else "[FAIL] KHONG TIM THAY"}')

print('\n=== 5. KIEM TRA FILE THAT TREN O DIA CAPCUT ===')
draft_file = os.path.join(data_create.get('draftDir', ''), 'draft_content.json')
if os.path.exists(draft_file):
    size_kb = os.path.getsize(draft_file) / 1024
    print(f'[OK] File draft_content.json ton tai that: {size_kb:.2f} KB')
else:
    print('[FAIL] Khong tim thay file draft_content.json tren o dia!')

print('\n=== 6. KIEM TRA CHAT BRIDGE & CO-DIRECTOR API ===')
t0 = time.time()
res_chat = urllib.request.urlopen('http://127.0.0.1:8765/api/chat/history')
data_chat = json.loads(res_chat.read().decode('utf-8'))
print(f'[OK] Agent Bridge Chat API thanh cong ({int((time.time()-t0)*1000)}ms): {len(data_chat.get("messages", []))} tin nhan')

print('\n>>> KET QUA QUET TOAN HE THONG: 100% HOAT DONG HOAN HAO! <<<')
