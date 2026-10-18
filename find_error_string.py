import os
import pathlib

apps_dir = pathlib.Path(os.environ.get('LOCALAPPDATA', '')) / 'CapCut' / 'Apps' / '9.6.0.4097'
print('Scanning in:', apps_dir)

keywords = [
    'đường dẫn của dự án',
    'Không thể dùng dự án',
    'Không dùng được dự án',
    'unusual path',
    'abnormal path',
    'comes from an unusual path'
]

matches = []
for root, dirs, files in os.walk(apps_dir):
    for f in files:
        if f.endswith(('.dll', '.exe', '.pak', '.dat', '.qm', '.json', '.bin')):
            fp = pathlib.Path(root) / f
            try:
                data = fp.read_bytes()
                for kw in keywords:
                    b_u8 = kw.encode('utf-8')
                    b_u16 = kw.encode('utf-16le')
                    if b_u8 in data or b_u16 in data:
                        matches.append((fp, kw))
                        print(f"FOUND '{kw}' in {fp.name}")
            except Exception:
                pass

print(f"Total matches: {len(matches)}")
