# 🎬 CapCut Web Studio & AI Co-Director MCP Suite

> Hệ thống Studio Web biên tập video CapCut thương mại chuẩn 13 Layers tích hợp AI Co-Director & giao thức MCP (Model Context Protocol).

---

## 🌟 Tính Năng Nổi Bật

1. **Timeline 13 Layers Tiêu Chuẩn CapCut Desktop:**
   - Hỗ trợ đầy đủ các track: Main Video (V1), Overlay PIP (V2, V3), Voice Off (A1), BGM Ducking (A2), Sound FX (A3), Auto-Captions (T1), Highlight Text (T2), Effects, Filters, Adjustment Layers.
   - Thao tác kéo thả, cắt tỉa (Trim handles), dao lam (Razor `B`), phím chọn (`V`), bắt dính (Snapping `S`), nam châm (Magnet `N`).

2. **AI Co-Director & Live QA Inspector:**
   - Tự động phát hiện lỗi theo tiêu chuẩn thương mại TikTok / Reels / Shorts:
     - Chạm vùng nguy hiểm viền dưới & góc biểu tượng (TikTok Lower-Third & Side Safe Zones).
     - Hook 3 giây đầu bị trễ, thiếu giật tít thị giác.
     - Lỗi xung đột âm lượng (Voice bị BGM đè, thiếu Audio Ducking).
     - Font chữ lỗi hiển thị hoặc cỡ chữ không chuẩn.
   - Tự động khắc phục 1-Click với AI Agent.

3. **OpenCV Forensic Footage Analyzer:**
   - Tự động quét toàn bộ kho footage thô bằng Computer Vision:
     - Đo tỷ lệ cháy sáng (Overexposure > 240) & thiếu sáng (Underexposure < 25).
     - Đo lường độ rung lắc camera (Inter-frame difference stability score).
     - Đo lường độ sắc nét (Laplacian variance focus test).
   - Tự động xếp hạng footage (A-Roll / B-Roll / Thẻ vàng / Loại bỏ).

4. **MCP (Model Context Protocol) Native Integration:**
   - Kết nối trực tiếp hai chiều với Claude / Gemini Antigravity IDE thông qua MCP Server.
   - Cho phép AI Agent tự động đọc kịch bản, lựa chọn footage tốt nhất và biên dịch timeline draft CapCut tự động.

---

## 🚀 Cài Đặt & Khởi Chạy

### 1. Yêu Cầu Hệ Thống
- Python 3.10+
- CapCut Desktop (bản PC quốc tế hoặc JianYing Pro)

### 2. Cài Đặt Thư Viện
```bash
pip install -r requirements.txt
```

### 3. Khởi Chạy Web Studio
```bash
python server.py
```
Mở trình duyệt tại: `http://127.0.0.1:8765`

---

## 📂 Cấu Trúc Dự Án

```
capcut-web-studio/
├── server.py              # FastAPI Backend, CapCut Draft Parser & MCP API
├── footage_analyzer.py    # OpenCV Computer Vision Engine phân tích footage
├── requirements.txt       # Danh sách thư viện Python
├── static/
│   ├── index.html         # Giao diện Web Studio chuẩn CapCut PC
│   ├── style.css          # CSS thiết kế Dark Mode, HSL Color Palette
│   └── app.js             # Logic Timeline, Playhead, Canvas & Audio Engine
└── README.md
```

---

## ⚖️ Giấy Phép
MIT License.
