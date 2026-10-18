import os
import pathlib
import json

capcut_dir = pathlib.Path(os.environ.get('LOCALAPPDATA', '')) / 'CapCut'
target_id = "DFB6AF57-BD90-426A-BAF8-EFE227AF6A8F"

print(f"Searching for {target_id} across CapCut User Data...")
for root, dirs, files in os.walk(capcut_dir / 'User Data'):
    for f in files:
        if f.endswith(('.json', '.ini', '.dat', '.txt')):
            fp = pathlib.Path(root) / f
            try:
                txt = fp.read_text(encoding='utf-8', errors='ignore')
                if target_id in txt:
                    print(f"Found in: {fp.relative_to(capcut_dir)}")
            except Exception:
                pass
