import shutil
import time
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_DRAFT_SRC = FIXTURES_DIR / "sample_draft"

@pytest.fixture(scope="session")
def live_server():
    import subprocess
    import socket
    
    # Kiểm tra xem port 8765 đã có server nào chạy chưa
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = False
    try:
        s.connect(("127.0.0.1", 8765))
        is_open = True
    except ConnectionRefusedError:
        is_open = False
    finally:
        s.close()
        
    proc = None
    if not is_open:
        proc = subprocess.Popen(["python", "server.py"], cwd=str(Path(__file__).parent.parent))
        # Đợi server sẵn sàng
        for _ in range(30):
            time.sleep(0.3)
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s2.connect(("127.0.0.1", 8765))
                s2.close()
                break
            except ConnectionRefusedError:
                s2.close()
                
    yield "http://127.0.0.1:8765"
    
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

@pytest.fixture(scope="session")
def sample_project_setup():
    from draft_io import detect_capcut_draft_base
    draft_base = detect_capcut_draft_base()
    target_dir = draft_base / "sample_draft"
    
    # Copy fixture vào draft_base để test
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(SAMPLE_DRAFT_SRC, target_dir)
    
    yield "sample_draft"
