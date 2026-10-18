import pathlib
import re

p = pathlib.Path(r'C:\Users\jinnr\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\BBSM_SET3_KB23\Timelines\DFB6AF57-BD90-426A-BAF8-EFE227AF6A8F\draft_info.json')
if p.exists():
    txt = p.read_text(encoding='utf-8', errors='ignore')
    matches = re.findall(r'BBSM_SET3_[a-zA-Z0-9_]+', txt)
    print('Project names mentioned in draft_info.json:', set(matches))
