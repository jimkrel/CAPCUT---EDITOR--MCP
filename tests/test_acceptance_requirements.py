import re
from pathlib import Path
from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

def test_acceptance_1_and_2_no_hardcoded_personal_data():
    """Nghiệm thu 2: Mở modal MCP trên máy sạch không có ô nào chứa jinnr hay BBSM_"""
    index_path = Path("static/index.html")
    content = index_path.read_text(encoding="utf-8")
    
    assert "jinnr" not in content.lower()
    assert "bbsm_" not in content.lower()
    assert "c:/users/" not in content.lower()
    
    # Kiểm tra input fields trong MCP modal không có giá trị hardcode
    mcp_inputs = re.findall(r'<input[^>]+id="mcp-[^"]+"[^>]*>', content)
    for inp in mcp_inputs:
        val_match = re.search(r'value="([^"]*)"', inp)
        if val_match:
            assert val_match.group(1) == "", f"Input has non-empty default value: {inp}"
            
    # Kiểm tra app.js
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    assert "jinnr" not in app_js.lower()
    assert "bbsm_" not in app_js.lower()
    assert "c:/users/" not in app_js.lower()

def test_acceptance_3_save_button_text_and_behavior():
    """Nghiệm thu 3: Nút Lưu có nhãn Lưu, tooltip an toàn, không còn toast đã xuất"""
    index_content = Path("static/index.html").read_text(encoding="utf-8")
    assert "Lưu" in index_content
    assert "Thay đổi được ghi trực tiếp vào draft CapCut" in index_content
    
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    assert "đã được đồng bộ trực tiếp vào draft CapCut" in app_js

def test_acceptance_4_toast_on_errors_and_capcut_running_state():
    """Nghiệm thu 4: Error toasts và banner CapCut running"""
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    # Kiểm tra các hàm catch đã bổ sung showToast error
    assert "showToast('Lỗi kết nối máy chủ CapCut Web Studio', 'error')" in app_js
    assert "CapCut đang mở — chỉnh sửa bị khóa" in app_js

def test_acceptance_5_scroll_and_selection_preservation():
    """Nghiệm thu 5: split và delete bảo toàn scrollLeft và selection"""
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    assert "savedScrollLeft" in app_js
    assert "scrollEl.scrollLeft = savedScrollLeft" in app_js
    assert "selectClip" in app_js

def test_acceptance_6_accessibility_and_font_size():
    """Nghiệm thu 6: modal có role dialog aria-modal, button có aria-label, font >= 11px"""
    index_content = Path("static/index.html").read_text(encoding="utf-8")
    assert 'role="dialog"' in index_content
    assert 'aria-modal="true"' in index_content
    
    css_content = Path("static/style.css").read_text(encoding="utf-8")
    # Tìm các font-size dưới 11px (ví dụ 8px, 9px, 10px)
    small_fonts = re.findall(r'font-size:\s*([0-9]+)px', css_content)
    for fs in small_fonts:
        assert int(fs) >= 11, f"Found font-size smaller than 11px: {fs}px"
    assert "#666;" not in css_content

def test_acceptance_xss_prevention_in_app_js():
    """Nghiệm thu 1: Các chỗ gán innerHTML nhạy cảm đều bọc qua esc()"""
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    
    # esc() function exists and sanitizes <, >, ", '
    assert "function esc(str)" in app_js
    assert ".replace(/&/g, '&amp;')" in app_js
    assert ".replace(/</g, '&lt;')" in app_js
    assert ".replace(/>/g, '&gt;')" in app_js
    assert ".replace(/\"/g, '&quot;')" in app_js
    
    # Component list bọc esc
    assert 'title="${esc(c.label)}">${esc(c.label)}' in app_js
    # Timeline clip bọc esc
    assert 'title="${esc(seg.label)}">${esc(seg.label)}' in app_js
    # QA card iss.message bọc esc
    assert '${esc(iss.message)}' in app_js
    # Tab Media bọc esc
    assert 'title="${esc(s.label)}">${esc(s.label)}' in app_js
    # Catch errors bọc esc
    assert '${esc(err.message)}' in app_js
