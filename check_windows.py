import win32gui
import win32process
import psutil

def enum_handler(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                results.append((hwnd, title, proc.name(), win32gui.GetWindowRect(hwnd)))
            except Exception:
                pass

windows = []
win32gui.EnumWindows(enum_handler, windows)
for w in windows:
    if 'capcut' in w[2].lower() or 'capcut' in w[1].lower():
        print(f'HWND: {w[0]}, Title: "{w[1]}", Proc: {w[2]}, Rect: {w[3]}')

print("Done scanning.")
