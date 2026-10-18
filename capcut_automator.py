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
    if not CAPCUT_EXE:
        return False
    if is_capcut_running():
        return True
    subprocess.Popen([str(CAPCUT_EXE)], creationflags=0x08)
    for _ in range(wait_sec * 2):
        time.sleep(0.5)
        if is_capcut_running():
            time.sleep(3)
            return True
    return False

def _navigate_home_pywinauto(app):
    try:
        dlg = app.top_level_windows()[0]
        dlg.set_focus()
        for name in ["Back", "Home", "Projects", "Thu vien", "Trang chu"]:
            try:
                btn = dlg.child_window(title=name, control_type="Button")
                if btn.exists(timeout=1):
                    btn.click_input()
                    time.sleep(1.2)
                    return True
            except Exception:
                pass
        dlg.type_keys("%{LEFT}")
        time.sleep(1)
        return True
    except Exception as e:
        logger.debug(f"navigate_home: {e}")
        return False

def _navigate_home_pyautogui():
    try:
        import pyautogui
        pyautogui.hotkey("alt", "left")
        time.sleep(0.8)
        pyautogui.press("escape")
        time.sleep(0.8)
        return True
    except Exception:
        return False

def _open_project_pywinauto(app, project_name):
    try:
        dlg = app.top_level_windows()[0]
        pname_lower = project_name.lower()
        for ctrl_type in ["Text", "DataItem", "ListItem", "Custom"]:
            try:
                items = dlg.descendants(control_type=ctrl_type)
                for item in items:
                    try:
                        txt = (item.window_text() or "").lower()
                        if pname_lower in txt:
                            item.double_click_input()
                            time.sleep(4)
                            logger.info(f"Opened '{project_name}' via {ctrl_type}")
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"open_project: {e}")
    return False

def open_project_in_capcut(project_name, wait_for_timeline_sec=6):
    if not is_capcut_running():
        if not launch_capcut(wait_sec=12):
            return {"ok": False, "error": "Khong the khoi dong CapCut.exe"}
        time.sleep(3)

    app = _get_capcut_window()
    if app:
        try:
            app.top_level_windows()[0].set_focus()
            time.sleep(0.5)
        except Exception:
            pass

    home_ok = _navigate_home_pywinauto(app) if app else False
    if not home_ok:
        _navigate_home_pyautogui()
    time.sleep(1.5)

    project_ok = _open_project_pywinauto(app, project_name) if app else False

    if not project_ok:
        return {
            "ok": False,
            "partial": True,
            "message": (
                f"CapCut da duoc mo va dieu huong ve Home. "
                f"Vui long click dup vao project '{project_name}' de mo timeline. "
                "UIAutomation khong tim thay card tu dong."
            ),
            "method": "manual_required"
        }

    time.sleep(wait_for_timeline_sec)
    return {
        "ok": True,
        "message": f"Da mo project '{project_name}' trong CapCut, timeline san sang.",
        "method": "ui_automation"
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
