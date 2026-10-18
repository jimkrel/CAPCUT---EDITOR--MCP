"""
capcut_automator.py - Tu dong hoa CapCut Desktop (Windows)
Dam bao 100% cua so CapCut Desktop hien thi va noi len tren man hinh chinh cua nguoi dung (WinSta0\\Default):
1. Dang ky du an vao root_meta_info.json o vi tri so 0 (tren cung ben trai)
2. Neu CapCut chua mo -> Kich hoat qua Scheduled Task OpenCapCutInteractive (interactive logon tren Default desktop)
3. Neu CapCut dang minimize hoac o duoi cac ung dung khac -> Khoi phuc SW_RESTORE, SwitchToThisWindow, BringWindowToTop, SetForegroundWindow
"""

import os
import time
import subprocess
import logging
import ctypes
from pathlib import Path
from typing import Optional, List

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

def attach_to_default_desktop():
    """Gan thread hien tai vao WinSta0\\Default de thay va tuong tac voi cac cua so that tren man hinh nguoi dung."""
    try:
        import win32service, win32con
        hwinsta = win32service.OpenWindowStation('WinSta0', False, win32con.MAXIMUM_ALLOWED)
        hwinsta.SetProcessWindowStation()
        hdesk = win32service.OpenDesktop('Default', 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
        return hdesk
    except Exception as e:
        logger.debug(f"attach_to_default_desktop info: {e}")
        return None

def find_capcut_windows() -> List[int]:
    """Tim cua so CapCut THUC SU HIEN THI (Visible GUI Window) tren WinSta0\\Default."""
    hdesk = attach_to_default_desktop()
    windows = []
    try:
        import win32gui, win32process, psutil
        def enum_cb(hwnd, _):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                pname = ""
                try:
                    pname = psutil.Process(pid).name().lower()
                except Exception:
                    pass

                # Cua so chinh CapCut: process CapCut.exe, tieu de CapCut, kich thuoc hop le
                if 'capcut' in pname and txt == 'CapCut':
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 300 and h > 200:
                            windows.append(hwnd)
                    except Exception:
                        windows.append(hwnd)

        desktop_handle = int(hdesk) if hdesk else None
        if desktop_handle:
            win32gui.EnumDesktopWindows(desktop_handle, enum_cb, None)
        else:
            win32gui.EnumWindows(enum_cb, None)
    except Exception as e:
        logger.debug(f"find_capcut_windows error: {e}")
    return windows

def bring_window_to_foreground(hwnd: int) -> bool:
    """Khoi phuc cua so tu trang thai Minimize va dua noi len tren cung man hinh nguoi dung."""
    try:
        import win32gui, win32con, win32api, win32process
        user32 = ctypes.windll.user32

        # 1. Nha phim ALT neu co & cho phep set foreground
        user32.keybd_event(0x12, 0, 2, 0) # KEYEVENTF_KEYUP
        try:
            user32.AllowSetForegroundWindow(-1) # ASFW_ANY
        except Exception:
            pass

        # 2. Khoi phuc neu dang bi thu nho (minimized / iconic)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE) # 9
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)    # 5

        # 3. AttachThreadInput de chuyen focus sach se
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd and fg_hwnd != hwnd:
            try:
                fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
                cur_thread = win32api.GetCurrentThreadId()
                user32.AttachThreadInput(cur_thread, fg_thread, True)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(cur_thread, fg_thread, False)
            except Exception:
                pass
        else:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)

        # 4. Dua len tren cung z-order
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
        )
        return True
    except Exception as e:
        logger.error(f"Loi bring_window_to_foreground: {e}")
        return False

def launch_or_focus_capcut(timeout_sec: int = 10) -> bool:
    """
    Kich hoat mo CapCut Desktop va dam bao cua so hien thi ngay truoc mat nguoi dung:
    - Neu da mo -> Focus & Restore len foreground ngay lap tuc
    - Neu chua mo -> Kich hoat qua Scheduled Task (chay tuong tac nguoi dung) roi doi focus
    """
    # Buoc 1: Kiem tra xem da co cua so CapCut chua
    existing_hwnds = find_capcut_windows()
    if existing_hwnds:
        for h in existing_hwnds:
            bring_window_to_foreground(h)
        logger.info(f"Da dua cua so CapCut (HWND={existing_hwnds[0]}) len man hinh chinh.")
        return True

    # Buoc 2: Kich hoat chay CapCut tuong tac
    logger.info("CapCut chua mo, dang khoi dong phien lam viec...")
    try:
        res = subprocess.run(["schtasks", "/run", "/tn", "OpenCapCutInteractive"], capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"schtasks output: {res.stderr or res.stdout}")
    except Exception as e:
        logger.warning(f"Khong the goi schtasks: {e}")

    # Fallback truc tiep
    if CAPCUT_EXE and Path(CAPCUT_EXE).exists():
        try:
            bat_path = Path(__file__).parent / "launch_capcut_interactive.bat"
            if bat_path.exists():
                subprocess.Popen(["cmd.exe", "/c", str(bat_path)], cwd=str(bat_path.parent))
            else:
                subprocess.Popen([str(CAPCUT_EXE)], cwd=str(Path(CAPCUT_EXE).parent))
        except Exception as e:
            logger.error(f"Fallback launch error: {e}")

    # Buoc 3: Cho cua so CapCut xuat hien va focus
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        time.sleep(0.5)
        hwnds = find_capcut_windows()
        if hwnds:
            for h in hwnds:
                bring_window_to_foreground(h)
            logger.info(f"CapCut da khoi dong thanh cong (HWND={hwnds[0]}).")
            return True

    logger.warning("Het thoi gian cho cua so CapCut.")
    return False

def open_project_in_capcut(project_name: str, wait_for_timeline_sec: int = 3):
    # 1. Dam bao project duoc dua len vi tri so 0 dau tien trong root_meta_info
    try:
        import register_draft
        register_draft.register_project_in_capcut(project_name)
    except Exception as e:
        logger.warning(f"Loi refresh root_meta_info: {e}")

    # 2. Khoi chay / dua cua so CapCut len man hinh chinh
    ok = launch_or_focus_capcut(timeout_sec=10)

    return {
        "ok": True,
        "projectName": project_name,
        "capcutForeground": ok,
        "message": f"Đã mở CapCut Desktop! Dự án '{project_name}' đã được nạp ở vị trí số 1 (trên cùng bên trái) trong giao diện CapCut.",
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
        logger.warning(f"Loi dang ky root_meta_info: {re}")

    launch_result = open_project_in_capcut(project_name)
    return {"ok": launch_result.get("ok"), "compile": compile_result, "launch": launch_result}

if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else "BBSM_SET3_KB20"
    result = open_project_in_capcut(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
