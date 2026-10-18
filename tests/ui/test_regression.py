import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_regression_suite(live_server, sample_project_setup):
    """
    Test hồi quy toàn diện theo yêu cầu Nghiệm Thu:
    - Space bật/tắt đúng 1 lần
    - Delete gửi đúng 1 request
    - Ctrl+B cắt và không đổi tool
    - Ctrl+Z/Ctrl+Y hoạt động
    - load project không tồn tại hiện error-card
    - phím tắt bị bỏ qua khi modal mở hoặc đang focus vào select/input
    - không có thẻ #xss1 nào trong DOM
    - không có alert()
    - không có chuỗi 'jinnr' hay 'BBSM_' trong HTML/JS
    """
    # 1. Kiểm tra chuỗi 'jinnr' và 'BBSM_' trong static/index.html và static/app.js
    html_text = Path("static/index.html").read_text(encoding="utf-8")
    js_text = Path("static/app.js").read_text(encoding="utf-8")
    
    assert "jinnr" not in html_text.lower(), "Tìm thấy 'jinnr' trong static/index.html"
    assert "bbsm_" not in html_text.lower(), "Tìm thấy 'BBSM_' trong static/index.html"
    assert "jinnr" not in js_text.lower(), "Tìm thấy 'jinnr' trong static/app.js"
    assert "bbsm_" not in js_text.lower(), "Tìm thấy 'BBSM_' trong static/app.js"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        # Bắt alert() và pageerror
        alerts_triggered = []
        page.on("dialog", lambda dialog: (alerts_triggered.append(dialog.message), dialog.dismiss()))
        
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        delete_requests = []
        page.on("request", lambda req: delete_requests.append(req.url) if "/api/delete-clip" in req.url else None)
        
        page.goto(live_server)
        page.wait_for_selector(".editor-shell")
        
        # Chọn project sample_draft
        page.select_option("#projectSelect", sample_project_setup)
        page.wait_for_selector(".timeline-clip")
        time.sleep(1.0)
        
        # 2. Kiểm tra XSS: không có thẻ #xss1 nào trong DOM
        assert page.locator("#xss1").count() == 0, "Lỗ hổng XSS: Thẻ #xss1 được render vào DOM!"
        
        # 3. Test Space bật/tắt đúng 1 lần
        is_playing_initial = page.evaluate("() => isPlaying")
        assert is_playing_initial is False
        
        page.keyboard.press("Space")
        time.sleep(0.3)
        is_playing_after_space = page.evaluate("() => isPlaying")
        assert is_playing_after_space is True, "Space lần 1 phải bắt đầu Play"
        
        page.keyboard.press("Space")
        time.sleep(0.3)
        is_playing_after_space2 = page.evaluate("() => isPlaying")
        assert is_playing_after_space2 is False, "Space lần 2 phải Tạm dừng (Pause)"
        
        # 4. Test Ctrl+B cắt và không đổi tool
        # Chọn clip sv2
        clip_sv2 = page.wait_for_selector('.timeline-clip[data-id="sv2"]')
        clip_sv2.click()
        time.sleep(0.3)
        
        initial_tool = page.evaluate("() => currentTool")
        with page.expect_response(lambda r: "/api/split-clip" in r.url and r.status == 200):
            page.keyboard.press("Control+b")
        page.wait_for_function("() => !isOperationPending")
        time.sleep(0.5)
        tool_after_split = page.evaluate("() => currentTool")
        assert tool_after_split == initial_tool, f"Ctrl+B làm đổi công cụ từ {initial_tool} sang {tool_after_split}"
        
        # 5. Test Ctrl+Z (Undo) và Ctrl+Y (Redo)
        # Bấm Ctrl+Z -> Hoàn tác cắt clip
        with page.expect_response(lambda r: "/api/undo/" in r.url and r.status == 200):
            page.keyboard.press("Control+z")
        page.wait_for_function("() => !isOperationPending")
        time.sleep(0.5)
        undo_toast = page.inner_text(".toast-item:last-child .toast-msg")
        assert "hoàn tác" in undo_toast.lower() or "undo" in undo_toast.lower() or "khôi phục" in undo_toast.lower()
        
        # Bấm Ctrl+Y -> Làm lại
        with page.expect_response(lambda r: "/api/redo/" in r.url and r.status == 200):
            page.keyboard.press("Control+y")
        page.wait_for_function("() => !isOperationPending")
        time.sleep(0.5)
        redo_toast = page.inner_text(".toast-item:last-child .toast-msg")
        assert "làm lại" in redo_toast.lower() or "redo" in redo_toast.lower()
        
        # 6. Test Delete gửi đúng 1 request
        # Chọn 1 clip (ví dụ st6)
        clip_st6 = page.locator('.timeline-clip[data-id="st6"]')
        if clip_st6.count() > 0:
            clip_st6.click()
            time.sleep(0.3)
            del_req_before = len(delete_requests)
            page.keyboard.press("Delete")
            time.sleep(0.8)
            del_req_after = len(delete_requests)
            assert del_req_after - del_req_before == 1, f"Delete phải gửi đúng 1 request, đã gửi: {del_req_after - del_req_before}"
            
        # 7. Phím tắt bị bỏ qua khi đang focus vào input hoặc khi modal mở
        # Focus vào ô tìm kiếm tài nguyên
        search_input = page.locator("#assetSearchInput")
        search_input.focus()
        page.keyboard.press("Space")
        time.sleep(0.2)
        # isPlaying không được bật lên
        assert page.evaluate("() => isPlaying") is False, "Phím tắt Space không được kích hoạt khi đang focus input"
        
        # Mở Shortcuts Help modal
        page.click("#btnHelpShortcuts")
        page.wait_for_selector("#shortcutsModal.open")
        page.keyboard.press("Space")
        time.sleep(0.2)
        assert page.evaluate("() => isPlaying") is False, "Phím tắt Space không được kích hoạt khi modal đang mở"
        page.keyboard.press("Escape")
        time.sleep(0.3)
        
        # 8. Load project không tồn tại hiện error-card
        page.evaluate("() => loadProject('NON_EXISTENT_PROJECT_XYZ')")
        page.wait_for_selector(".project-error-card", state="visible")
        err_card_text = page.inner_text(".project-error-card")
        assert "không" in err_card_text.lower() or "lỗi" in err_card_text.lower() or "thể tải" in err_card_text.lower()
        
        # 9. Đảm bảo không có alert() nào và không có pageerror
        assert len(alerts_triggered) == 0, f"Phát hiện hàm alert() bị gọi: {alerts_triggered}"
        assert len(page_errors) == 0, f"Phát hiện pageerror: {page_errors}"
        
        browser.close()
