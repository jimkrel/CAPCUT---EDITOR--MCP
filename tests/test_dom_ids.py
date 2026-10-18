import re
from pathlib import Path

def test_no_missing_dom_ids():
    """
    Test A1: Toàn bộ document.getElementById(...) trong app.js
    phải tồn tại trong static/index.html (hoặc nằm trong whitelist có lý do rõ ràng).
    """
    app_js_path = Path("static/app.js")
    index_html_path = Path("static/index.html")
    
    assert app_js_path.exists(), "static/app.js not found"
    assert index_html_path.exists(), "static/index.html not found"
    
    app_js = app_js_path.read_text(encoding="utf-8")
    index_html = index_html_path.read_text(encoding="utf-8")
    
    # Lấy mọi getElementById('...')
    js_ids = set(re.findall(r'document\.getElementById\([\'"]([a-zA-Z0-9_\-]+)[\'"]\)', app_js))
    html_ids = set(re.findall(r'id=[\'"]([a-zA-Z0-9_\-]+)[\'"]', index_html))
    
    # Whitelist cho các ID được sinh động trong JS runtime hoặc test helper
    # Mỗi ID trong whitelist phải có chú thích lý do
    ID_WHITELIST = {
        # Ví dụ: 'toastContainer' được tạo động qua getToastContainer() nếu chưa có
        "toastContainer": "Container toast được tạo động qua DOM API khi chưa có",
    }
    
    missing_ids = (js_ids - html_ids) - set(ID_WHITELIST.keys())
    assert len(missing_ids) == 0, f"Phát hiện các DOM ID trong app.js nhưng thiếu trong index.html: {sorted(list(missing_ids))}"

def test_no_duplicate_function_declarations():
    """
    Test A3: Mỗi tên hàm trong app.js chỉ được khai báo duy nhất một lần.
    """
    app_js_path = Path("static/app.js")
    app_js = app_js_path.read_text(encoding="utf-8")
    
    matches = re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', app_js)
    counts = {}
    for fn in matches:
        counts[fn] = counts.get(fn, 0) + 1
        
    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert len(duplicates) == 0, f"Phát hiện hàm bị khai báo trùng lặp trong app.js: {duplicates}"
