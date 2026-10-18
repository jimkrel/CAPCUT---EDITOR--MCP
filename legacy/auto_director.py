"""
auto_director.py - Trinh Dieu Phien Tu Dong Hoa CapCut Desktop Truc Tiep (Khong Can Web)

Chuc nang:
1. Nhan kich ban thoai + thu muc B-Roll tu dong hoac tham so dong lenh
2. Tu dong phan tich WPM va chia nhip cat (Fast/Medium/Slow hoac so giay tuy chon)
3. Tu dong bien dich du an 13 Layer CapCut Desktop (VJ, B-roll Zero-Duplicate, Mau Studio LUT Track 7, Subtitle Montserrat Safe Zone Track 10, Ducking BGM Track 9)
4. Dang ky truc tiep vao file tong `root_meta_info.json` cua CapCut Desktop (Vi tri so 1 dau tien)
5. Khoi dong CapCut Desktop de mo du an ngay truoc mat ban!

Cach dung:
  python auto_director.py
  hoac:
  python auto_director.py --name "Du_An_01" --script "Kich ban..." --broll "C:/Footage"
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import footage_analyzer
from register_draft import register_project_in_capcut
from capcut_automator import open_project_in_capcut, launch_capcut

def run_auto_director(
    project_name: str,
    raw_script: str,
    broll_folder: str = "",
    vj_video: str = "",
    bgm_path: str = "",
    hook_text: str = "",
    cta_text: str = "",
    pacing: str = "2.5s",
    open_capcut: bool = True
):
    print("=" * 60)
    print(f"🎬 [CAPCUT AUTO-DIRECTOR] KHOI CHAY BIEN DICH DU AN: {project_name}")
    print("=" * 60)

    # 1. Phan tich kich ban
    print(f"[1/4] Dang phan tich kich ban theo nhip: {pacing}...")
    sentences = footage_analyzer.parse_commercial_script(raw_script, pacing_mode=pacing)
    print(f"✓ Da chia thanh {len(sentences)} phan canh VJ & B-Roll.")
    for i, s in enumerate(sentences):
        print(f"   [{s.get('type').upper()}] ({s.get('durationSec')}s): {s.get('text')}")

    # 2. Bien dich 13 Layer qua MCP
    print(f"\n[2/4] Dang bien dich 13 Layer CapCut Desktop...")
    runner_js = BASE_DIR / "mcp_runner.js"
    server_js = BASE_DIR / "capcut_mcp_server.js"
    
    payload = {
        "projectName": project_name,
        "vjVideoPath": vj_video,
        "brollFolderPath": broll_folder,
        "bgmPath": bgm_path,
        "hookText": hook_text,
        "ctaText": cta_text,
        "scriptSentences": sentences
    }
    
    import tempfile
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as tf:
        json.dump({"action": "create_project", "toolName": "capcut_compile_13layer_draft", "args": payload}, tf, ensure_ascii=False)
        temp_input = tf.name

    try:
        proc = subprocess.run(["node", str(runner_js), str(server_js), temp_input], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout.strip())
        if not res.get("ok"):
            print("✗ Loi bien dich MCP:", res.get("error"))
            return False
        print(f"✓ Da tao thanh cong file du an tai: {res.get('draftDir')}")
    finally:
        if os.path.exists(temp_input):
            try: os.unlink(temp_input)
            except Exception: pass

    # 3. Dang ky vao file tong root_meta_info.json cua CapCut Desktop
    print(f"\n[3/4] Dang dang ky du an vao trang chu CapCut Desktop (root_meta_info.json)...")
    reg_res = register_project_in_capcut(project_name)
    if reg_res.get("ok"):
        print(f"✓ Da dang ky thanh cong! Du an da nam o vi tri so 1 tren CapCut Desktop.")
    else:
        print(f"⚠ Canh bao dang ky: {reg_res.get('error')}")

    # 4. Mo CapCut Desktop
    if open_capcut:
        print(f"\n[4/4] Dang khoi dong CapCut Desktop...")
        launch_res = open_project_in_capcut(project_name)
        print(f"✓ {launch_res.get('message', 'CapCut Desktop da duoc kich hoat!')}")
        print("\n" + "=" * 60)
        print("🎉 HOAN TAT! Du an da san sang tren CapCut Desktop cua ban.")
        print("   Ban chi can click vao du an o vi tri dau tien tren man hinh CapCut de tiep tuc.")
        print("=" * 60)

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Director CLI cho CapCut Desktop")
    parser.add_argument("--name", default="", help="Ten du an CapCut")
    parser.add_argument("--script", default="", help="Noi dung kich ban hoac duong dan file .txt")
    parser.add_argument("--broll", default="", help="Duong dan thu muc footage B-Roll")
    parser.add_argument("--vj", default="", help="Duong dan video VJ nguoi noi")
    parser.add_argument("--bgm", default="", help="Duong dan file nhac nen BGM")
    parser.add_argument("--hook", default="", help="Cau hook 3 giay dau")
    parser.add_argument("--cta", default="", help="Cau keu goi hanh dong CTA outro")
    parser.add_argument("--pacing", default="2.5s", help="Nhip cat (vi du: 1.5s, 2.0s, 2.5s...)")
    parser.add_argument("--no-launch", action="store_true", help="Khong tu dong mo CapCut sau khi tao")

    args = parser.parse_args()

    # Kiem tra kich ban
    script_text = args.script.strip()
    if script_text and os.path.exists(script_text) and os.path.isfile(script_text):
        with open(script_text, "r", encoding="utf-8") as f:
            script_text = f.read()

    # Neu chay truc tiep khong tham so -> Chay interactive nhap lieu don gian
    if not script_text:
        print("--- CAPCUT DESKTOP AUTO DIRECTOR ---")
        script_text = """Ban co biet ly do tra sua o day luon dong khach khong?
[BROLL] Can canh pha che tra sua tran chau hoang kim boc khoi da lanh.
Huong vi dam da nguyen ban tu la tra tuoi huu co tuyen chon.
[BROLL] Khach hang tuoi cuoi thuong thuc ly nuoc thom ngon.
Uu dai giam 30% cho khach hang ghe quan ngay hom nay!"""
        print("Su dung kich ban mau (F&B Tra Sua):\n", script_text)

    proj_name = args.name.strip() or f"AUTO_CAPCUT_{int(time.time())}"

    run_auto_director(
        project_name=proj_name,
        raw_script=script_text,
        broll_folder=args.broll.strip(),
        vj_video=args.vj.strip(),
        bgm_path=args.bgm.strip(),
        hook_text=args.hook.strip() or "TRÀ SỮA ĐẬM VỊ ĐÔNG KHÁCH",
        cta_text=args.cta.strip() or "GHÉ QUÁN NHẬN NGAY ƯU ĐÃI 30%",
        pacing=args.pacing.strip(),
        open_capcut=not args.no_launch
    )
