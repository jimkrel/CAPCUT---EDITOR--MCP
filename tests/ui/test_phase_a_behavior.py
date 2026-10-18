import shutil
import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_DRAFT_SRC = FIXTURES_DIR / "sample_draft"

@pytest.fixture(scope="module")
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
        proc = subprocess.Popen(["python", "server.py"], cwd=str(Path(__file__).parent.parent.parent))
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

@pytest.fixture(scope="module")
def sample_project_setup():
    from draft_io import detect_capcut_draft_base
    draft_base = detect_capcut_draft_base()
    target_dir = draft_base / "sample_draft"
    
    # Copy fixture vào draft_base để test
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(SAMPLE_DRAFT_SRC, target_dir)
    
    yield "sample_draft"
    
    # Dọn dẹp sau khi test
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

def test_a_test_1_and_a3_behavior(live_server, sample_project_setup):
    proj_name = sample_project_setup
    page_errors = []
    console_errors = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        page.goto("http://127.0.0.1:8765/")
        page.wait_for_selector("#projectSelect")
        
        # Chọn project sample_draft
        page.select_option("#projectSelect", proj_name)
        time.sleep(1.0)
        
        # 1. Test click clip sv2 (Video clip thứ 2, bắt đầu lúc 8.0s)
        clip_sv2 = page.wait_for_selector('.timeline-clip[data-id="sv2"]')
        assert clip_sv2 is not None, "Clip sv2 not found on timeline"
        clip_sv2.click()
        time.sleep(0.5)
        
        # Kiểm tra playhead và inspector
        playhead_us = page.evaluate("() => currentPlayheadUs")
        assert playhead_us == 8000000, f"Expected playhead at 8000000 us, got {playhead_us}"
        
        time_range_text = page.locator("#inspTimeRange").inner_text()
        assert "8.00s ➔ 16.00s" in time_range_text, f"Expected 8.00s ➔ 16.00s, got {time_range_text}"
        
        track_badge_text = page.locator("#inspTrackBadge").inner_text()
        assert "Track" in track_badge_text, f"Unexpected track badge: {track_badge_text}"
        
        # 2. Test click text clip st2 (Text clip bắt đầu lúc 4.0s)
        clip_st2 = page.wait_for_selector('.timeline-clip[data-id="st2"]')
        assert clip_st2 is not None, "Clip st2 not found on timeline"
        clip_st2.click()
        time.sleep(0.5)
        
        time_range_st2 = page.locator("#inspTimeRange").inner_text()
        assert "4.00s ➔ 8.00s" in time_range_st2, f"Expected 4.00s ➔ 8.00s, got {time_range_st2}"
        
        # 3. Test cắt clip bằng Ctrl+B
        page.keyboard.press("Control+b")
        time.sleep(1.0)
        
        # Kiểm tra toast: không có toast-error
        error_toasts = page.locator(".toast-error").all()
        assert len(error_toasts) == 0, f"Unexpected error toast after split: {[t.inner_text() for t in error_toasts]}"
        
        # 4. Test A3: Khung TikTok
        guide = page.locator("#tiktokSafeGuide")
        btn_guide = page.locator("#btnToggleSafeGuide")
        
        # Trạng thái ban đầu: không hiển thị
        box_init = guide.bounding_box()
        assert box_init is None or box_init["width"] == 0 or not guide.is_visible()
        
        # Bấm lần 1: hiện khung
        btn_guide.click()
        time.sleep(0.3)
        assert guide.is_visible(), "TikTok safe guide should be visible after click"
        box_active = guide.bounding_box()
        assert box_active is not None and box_active["width"] > 0 and box_active["height"] > 0
        assert btn_guide.get_attribute("aria-pressed") == "true"
        
        # Bấm lần 2: ẩn khung
        btn_guide.click()
        time.sleep(0.3)
        assert not guide.is_visible(), "TikTok safe guide should be hidden after second click"
        assert btn_guide.get_attribute("aria-pressed") == "false"
        
        browser.close()
        
    assert len(page_errors) == 0, f"Page errors encountered: {page_errors}"


def test_a2_mcp_footage_scan_ui(live_server, sample_project_setup, tmp_path):
    footage_dir = tmp_path / "test_footages"
    footage_dir.mkdir(parents=True, exist_ok=True)
    sample_mp4 = footage_dir / "sample_test.mp4"
    sample_mp4.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00"*200)

    page_errors = []
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto("http://127.0.0.1:8765/")
        page.wait_for_selector("#projectSelect")
        page.select_option("#projectSelect", sample_project_setup)
        time.sleep(0.5)

        # Mở modal MCP Studio
        btn_mcp = page.locator("button.btn-hdr:has-text('MCP Studio')")
        btn_mcp.click()
        time.sleep(0.5)

        mcp_modal = page.locator("#mcpModal")
        assert mcp_modal.is_visible(), "MCP Modal should be visible"

        # Điền đường dẫn folder footage vào #mcpBrollFolder
        page.fill("#mcpBrollFolder", str(footage_dir))
        
        # Bấm nút 'Quét Lọc Lỗi'
        btn_scan = page.locator("button.mcp-btn-action:has-text('Quét Lọc Lỗi')")
        btn_scan.click()
        
        # Chờ kết quả hiển thị
        time.sleep(2.0)
        
        # Kiểm tra không có lỗi 'Lỗi quét folder'
        content = page.locator("#mcpFootageCardsGrid").inner_text()
        assert "Lỗi quét folder" not in content, f"Unexpected error message in grid: {content}"
        
        # Kiểm tra bộ đếm Scanned >= 1
        scanned_count = page.locator("#diagTotalScanned").inner_text()
        assert int(scanned_count) >= 1, f"Expected diagTotalScanned >= 1, got {scanned_count}"

        # Kiểm tra thẻ footage xuất hiện
        cards = page.locator(".mcp-footage-card").all()
        assert len(cards) >= 1, "At least one footage card should be rendered"

        browser.close()

    assert len(page_errors) == 0, f"Page errors in A2 test: {page_errors}"

