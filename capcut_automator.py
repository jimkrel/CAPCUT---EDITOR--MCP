"""
capcut_automator.py - Tu dong hoa CapCut Desktop (Windows)
1. Khoi chay CapCut.exe neu chua mo
2. Neu CapCut dang o HOME → dieu huong vao project vua compile
3. Neu CapCut dang mo project khac → ve HOME roi mo project moi
4. KHONG can dong/mo lai CapCut
"""

import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("capcut_automator")

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")

def _find_capcut_exe():
    apps_dir = Path(LOCALAPPDATA) / "CapCut" / "Apps"
    if not apps_dir.exists():
        return None
    for d in sorted(apps_dir.iterdir(), reverse=True):
        c = d / "CapCut.exe"
        if c.exists():
            return c
    flat = apps_dir / "CapCut.exe"
    return flat if flat.exists() else None

CAPCUT_EXE = _find_capcut_exe()

def is_capcut_running():
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq CapCut.exe"],
            text=True, creationflags=0x08000000
        )
        return "CapCut.exe" in out
    except Exception:
        return False

def _get_capcut_window():
    try:
        from pywinauto import Application, findwindows
        handles = findwindows.find_windows(title_re=".*CapCut.*")
        if handles:
            return Application(backend="uia").connect(handle=handles[0])
    except Exception as e:
        logger.debug(f"find_window: {e}")
    return None

def launch_capcut(wait_sec=10):
    if is_capcut_running():
        return True

    if not CAPCUT_EXE or not Path(CAPCUT_EXE).exists():
        logger.error("Không tìm thấy CapCut.exe trên máy")
        return False

    exe_path = str(CAPCUT_EXE)
    exe_dir = str(Path(CAPCUT_EXE).parent)

    try:
        subprocess.Popen([exe_path], cwd=exe_dir)
        logger.info(f"Đã kích hoạt khởi chạy CapCut: {exe_path} (cwd: {exe_dir})")
    except Exception as e:
        logger.error(f"Lỗi khởi chạy CapCut: {e}")
        return False

    for _ in range(wait_sec * 2):
        time.sleep(0.5)
        if is_capcut_running():
            return True
    return False

def open_project_in_capcut(project_name, wait_for_timeline_sec=3):
    # 1. Đảm bảo project được đưa lên vị trí số 0 đầu tiên trong root_meta_info
    try:
        import register_draft
        register_draft.register_project_in_capcut(project_name)
    except Exception as e:
        logger.warning(f"Lỗi refresh root_meta_info: {e}")

    # 2. Luôn kích hoạt mở hoặc đưa cửa sổ CapCut lên màn hình chính
    launch_capcut(wait_sec=8)

    # 3. Thử điều hướng tự động nếu bắt được handle
    app = _get_capcut_window()
    if app:
        try:
            app.top_level_windows()[0].set_focus()
            _open_project_pywinauto(app, project_name)
        except Exception:
            pass

    return {
        "ok": True,
        "projectName": project_name,
        "message": f"Đã mở CapCut Desktop! Dự án '{project_name}' đã được nạp ở vị trí đầu tiên (trên cùng bên trái).",
        "position": 0
    }

def compile_and_open(project_name, script_sentences, vj_video_path="", broll_folder="", bgm_path="", hook_text="", cta_text=""):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from capcut_mcp_server import compile13LayerCommercialDraft

    for s in script_sentences:
        if "durationUs" not in s and "durationSec" in s:
            s["durationUs"] = int(s["durationSec"] * 1_000_000)
        if "rawStartUs" not in s and "startSec" in s:
            s["rawStartUs"] = int(s["startSec"] * 1_000_000)

    compile_result = compile13LayerCommercialDraft({
        "projectName": project_name,
        "vjVideoPath": vj_video_path,
        "brollFolderPath": broll_folder,
        "bgmPath": bgm_path,
        "hookText": hook_text,
        "ctaText": cta_text,
        "scriptSentences": script_sentences
    })

    if not compile_result.get("ok"):
        return {"ok": False, "step": "compile", "error": compile_result.get("error")}

    try:
        from register_draft import register_project_in_capcut
        register_project_in_capcut(project_name)
    except Exception as re:
        logger.warning(f"Lỗi đăng ký root_meta_info: {re}")

    launch_result = open_project_in_capcut(project_name)
    return {"ok": launch_result.get("ok"), "compile": compile_result, "launch": launch_result}

if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python capcut_automator.py <project_name>")
        sys.exit(1)
    result = open_project_in_capcut(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
