# 🎬 CapCut Web Studio & AI Co-Director MCP Suite

> Hệ thống Studio Web biên tập video CapCut thương mại chuẩn 13 Layers tích hợp AI Co-Director & giao thức MCP (Model Context Protocol).

---

## ⚠️ CẢNH BÁO QUAN TRỌNG TRƯỚC KHI SỬ DỤNG
> [!IMPORTANT]
> **Vui lòng ĐÓNG ứng dụng CapCut Desktop hoặc JianYing Pro trước khi thực hiện các thao tác chỉnh sửa hoặc ghi draft** (như cắt clip, cập nhật, xóa, auto-fix, hoàn tác/làm lại).
> Ứng dụng CapCut Desktop giữ khoá file draft trong bộ nhớ, nếu ghi đè trong lúc CapCut đang mở có thể làm mất dữ liệu hoặc xung đột file draft. Hệ thống Backend và MCP Server sẽ tự động phát hiện process và trả mã lỗi `HTTP 409 Conflict` nếu CapCut đang chạy.

---

## 🌟 Tính Năng Nổi Bật

1. **Timeline 13 Layers Tiêu Chuẩn CapCut Desktop:**
   - Hỗ trợ đầy đủ các track: Main Video (V1), Overlay PIP (V2, V3), Voice Off (A1), BGM Ducking (A2), Sound FX (A3), Auto-Captions (T1), Highlight Text (T2), Effects, Filters, Adjustment Layers.
   - Hỗ trợ preview âm thanh đồng bộ với Playhead, hiển thị đa lớp video trên cùng, đo FPS và Color Space chuẩn xác từ file draft gốc.
   - Thao tác kéo thả, cắt tỉa (Trim handles), dao lam (`B`), phím chọn (`V`), bắt dính (Snapping `S`), nam châm (Magnet `N`).

2. **AI Co-Director & Live QA Inspector:**
   - Tự động phát hiện lỗi theo tiêu chuẩn thương mại TikTok / Reels / Shorts:
     - **Safe Zone TikTok**: Chạm vùng nguy hiểm viền dưới (`y < -0.42`) hoặc mép trên notch camera (`y > 0.44`).
     - **Montserrat Shadow**: Phụ đề thiếu bóng đổ thương mại -45 độ chuẩn.
     - **Letterbox**: Phát hiện footage viền đen (`scale < 1.0x`) để tự động punch-in zoom 1.15x.
     - **Dead Outro Gap**: Phát hiện đuôi video chết dài sau khi dứt lời thoại.
   - **Gộp nhóm lỗi thông minh**: Gom hàng chục lỗi cùng nhóm kèm tính năng "Sửa tất cả" hoặc sửa từng vị trí, nhảy Playhead và bounding box trực quan.

3. **OpenCV Forensic Footage Analyzer:**
   - Quét mẫu trải đều 12 frame trên toàn bộ video clip.
   - **Đo rung lắc toàn cục camera**: Sử dụng thuật toán `cv2.phaseCorrelate` kèm cửa sổ Hanning trên các cặp frame liền kề, không bị đo sai khi vật thể chuyển động.
   - **Đo độ nét chuẩn xác**: Tính toán biến sai Laplacian trên top 20% block tương phản cao nhất. Cảnh trơn/ít texture không bị kết luận mất nét sai.
   - **Chống cháy sáng thông minh**: Phân biệt nền trắng studio (vẫn giữ chi tiết texture) với cháy sáng thật sự (pixel ≥ 250 và std ≤ 3.0). Hỗ trợ profile `"default"` và `"white_bg"`.

4. **MCP (Model Context Protocol) Native Integration:**
   - Cung cấp `mcp_server.py` chuẩn SDK Python `mcp` chạy qua stdio, kết nối mượt mà với **Claude Desktop**, **Antigravity IDE**, **Cursor** hoặc bất kỳ AI Agent nào.
   - 8 Tools tích hợp: `list_projects`, `get_project`, `audit_project`, `analyze_footage_folder`, `split_clip`, `update_clip`, `delete_clip`, `auto_fix`.

---

## ⌨️ Bảng Phím Tắt Bàn Phím (Keyboard Shortcuts)

| Phím Tắt | Chức Năng |
| :--- | :--- |
| `Space` | Phát / Tạm dừng video (Play / Pause) |
| `V` | Chuyển công cụ **Con trỏ chọn** (Selection tool) |
| `B` | Chuyển công cụ **Dao lam** (Razor tool) |
| `Ctrl + B` | **Cắt clip tại vị trí Playhead** (Split at playhead) |
| `Delete` / `Backspace` | **Xóa clip đang chọn** (Có toast Hoàn tác 6 giây) |
| `Ctrl + Z` | **Hoàn tác** (Undo - lưu tối đa 20 bước trong `.history/`) |
| `Ctrl + Shift + Z` hoặc `Ctrl + Y` | **Làm lại** (Redo) |
| `Ctrl + D` | **Nhân đôi clip** (Duplicate clip) |
| `←` / `→` | Lùi / Tiến **1 frame** (theo đúng FPS thực tế của dự án) |
| `Shift + ←` / `Shift + →` | Lùi / Tiến **1 giây** |
| `Esc` | Đóng Modal hoặc Bỏ chọn clip |

---

## ⚙️ Cấu Hình Biến Môi Trường (Environment Variables)

| Tên Biến | Mặc Định | Mô Tả |
| :--- | :--- | :--- |
| `CAPCUT_DRAFTS_DIR` | Tự động dò tìm | Đường dẫn thư mục chứa các dự án CapCut PC / JianYing Pro. Nếu không đặt, hệ thống tự động dò tìm trong `%LOCALAPPDATA%/CapCut` hoặc `Movies/CapCut`. |
| `CAPCUT_MCP_JS` | `C:/Users/jinnr/...` | *(Tuỳ chọn)* Đường dẫn file script Node.js legacy nếu chạy qua cầu nối Node wrapper. |

---

## 🚀 Cài Đặt & Khởi Chạy

### 1. Yêu Cầu Hệ Thống
- Python 3.10+
- Hệ điều hành Windows hoặc macOS
- CapCut Desktop hoặc JianYing Pro
- Node.js (tuỳ chọn, chỉ cần nếu bạn sử dụng legacy Node MCP wrapper)

### 2. Cài Đặt Thư Viện Python
```bash
pip install -r requirements.txt
```

### 3. Khởi Chạy Web Studio
```bash
python server.py
```
Mở trình duyệt tại: `http://127.0.0.1:8765`

### 4. Kết Nối MCP Server Với Claude Desktop / Antigravity IDE

#### Cách 1: Sử dụng lệnh `claude mcp add`
```bash
claude mcp add capcut-web-studio python C:/path/to/capcut-web-studio/mcp_server.py
```

#### Cách 2: Thêm vào file cấu hình `claude_desktop_config.json`
```json
{
  "mcpServers": {
    "capcut-web-studio": {
      "command": "python",
      "args": [
        "C:/Users/jinnr/.gemini/antigravity-ide/scratch/capcut-web-studio/mcp_server.py"
      ]
    }
  }
}
```

---

## 📂 Cấu Trúc Dự Án Sau Tối Ưu

```
capcut-web-studio/
├── server.py              # FastAPI Backend, Static hosting, Security & API endpoints
├── draft_io.py            # Module dùng chung: Đọc/ghi CapCut draft an toàn, Undo/Redo, Clip ops
├── audit.py               # Module dùng chung: Kiểm định kịch bản, Safe Zone TikTok & Auto-fix
├── mcp_server.py          # Native MCP Server (FastMCP / MCPServer) giao tiếp qua stdio
├── footage_analyzer.py    # OpenCV Computer Vision Engine phân tích footage (phaseCorrelate, focus, overexposure)
├── mcp_runner.js          # An toàn hoá bộ chạy Node.js legacy chống injection
├── requirements.txt       # Danh sách thư viện Python (FastAPI, psutil, opencv, numpy, mcp, pytest)
├── static/
│   ├── index.html         # Giao diện 3 cột chuyên nghiệp, Header 48px, Transport timecode độc nhất
│   ├── style.css          # Design Tokens chuẩn Minimal Dark (Figma/Linear), không neon chói
│   └── app.js             # Bộ xử lý tương tác UI, Toasts thông minh, Single keydown listener, Synchronized audio
├── tests/
│   ├── test_phase1_security.py  # Test bảo mật: Whitelist tool, CORS 403, Path traversal, Media whitelist
│   ├── test_phase2_backend.py   # Test backend: Null clip handling, Process lock 409, Split material clone, Undo/Redo
│   ├── test_phase3_analyzer.py  # Test footage analyzer: 4 synthetic test cases theo kịch bản chuẩn
│   └── test_phase6_mcp.py       # Test MCP Server: 5/5 tools test với FastMCP stdio
└── README.md
```

---

## ⚖️ Giấy Phép
Dự án được phân phối dưới giấy phép MIT License.
