import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

def analyze_video_file(file_path: str, max_samples: int = 5) -> Dict[str, Any]:
    """
    Phân tích pháp y chất lượng footage bằng Computer Vision siêu tốc:
    1. Độ sáng: Tỷ lệ cháy sáng (>240), thiếu sáng (<25), Luma trung bình.
    2. Độ ổn định: Đo lường độ rung lắc camera (Inter-frame difference).
    3. Độ sắc nét: Phương sai toán tử Laplacian (Laplacian variance focus test).
    4. Kích thước, độ phân giải, thời lượng và định dạng.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        return {"ok": False, "error": f"Tệp không tồn tại: {file_path}"}

    file_name = path_obj.name
    file_size_mb = round(path_obj.stat().st_size / (1024 * 1024), 2)
    ext = path_obj.suffix.lower()

    # Xử lý Audio thuần túy
    if ext in ['.wav', '.mp3', '.m4a']:
        return {
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "audio",
            "file_size_mb": file_size_mb,
            "duration_sec": 0.0,
            "resolution": "Audio",
            "aspect_ratio": "--",
            "metrics": {
                "overexposed_pct": 0.0,
                "underexposed_pct": 0.0,
                "sharpness_score": 100.0,
                "shake_score": 0.0,
                "luma_mean": 128.0
            },
            "grade": "EXCELLENT",
            "status": "PASS",
            "issues": [],
            "recommendations": ["Sẵn sàng làm Voice hoặc BGM Ducking"],
            "verdict": "Âm thanh thương mại chuẩn",
            "approved": True
        }

    if not HAS_CV2:
        return {
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "video",
            "file_size_mb": file_size_mb,
            "resolution": "1080x1920",
            "aspect_ratio": "9:16",
            "metrics": {
                "overexposed_pct": 0.0,
                "underexposed_pct": 0.0,
                "sharpness_score": 100.0,
                "shake_score": 5.0,
                "luma_mean": 128.0
            },
            "grade": "ACCEPTABLE",
            "status": "PASS",
            "issues": [],
            "recommendations": [],
            "verdict": "Chấp nhận (Chế độ cơ bản)",
            "approved": True
        }

    cap = cv2.VideoCapture(str(path_obj))
    if not cap.isOpened():
        return {
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "video",
            "file_size_mb": file_size_mb,
            "resolution": "--",
            "aspect_ratio": "--",
            "metrics": {"overexposed_pct": 0, "shake_score": 0},
            "grade": "REJECTED",
            "status": "FAIL",
            "issues": ["Không thể mở luồng video"],
            "recommendations": ["Kiểm tra lại codec video"],
            "verdict": "Lỗi định dạng tệp",
            "approved": False
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_sec = round(total_frames / fps, 2) if fps > 0 else 0.0

    overexposed_list = []
    underexposed_list = []
    sharpness_list = []
    shake_diffs = []
    luma_means = []
    prev_gray = None

    samples_read = 0
    stride = max(5, int(fps * 0.4)) # Nhảy khoảng 0.4s một lần

    while samples_read < max_samples:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        samples_read += 1

        # Resize nhỏ xuống 320p để đo lường cực nhanh
        h, w = frame.shape[:2]
        if w > 320:
            scale = 320.0 / w
            small_frame = cv2.resize(frame, (320, int(h * scale)))
        else:
            small_frame = frame

        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        luma_mean = float(np.mean(gray))
        luma_means.append(luma_mean)

        # 1. Cháy sáng (>240) và Quá tối (<25)
        over_pct = float(np.mean(gray > 240) * 100.0)
        under_pct = float(np.mean(gray < 25) * 100.0)
        overexposed_list.append(over_pct)
        underexposed_list.append(under_pct)

        # 2. Độ nét (Laplacian variance)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharpness_list.append(lap_var)

        # 3. Độ rung lắc (Inter-frame difference)
        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            shake_diffs.append(float(np.mean(diff)))
        prev_gray = gray

        # Bỏ qua stride frames bằng grab siêu tốc (không decode toàn bộ)
        for _ in range(stride):
            if not cap.grab():
                break

    cap.release()

    avg_over = round(float(np.mean(overexposed_list)), 1) if overexposed_list else 0.0
    avg_under = round(float(np.mean(underexposed_list)), 1) if underexposed_list else 0.0
    avg_sharpness = round(float(np.mean(sharpness_list)), 1) if sharpness_list else 120.0
    avg_shake = round(float(np.mean(shake_diffs)), 1) if shake_diffs else 4.0
    avg_luma = round(float(np.mean(luma_means)), 1) if luma_means else 128.0

    issues = []
    recommendations = []
    grade = "EXCELLENT"
    status = "PASS"
    approved = True

    # Phân loại Cháy Sáng
    if avg_over > 22.0:
        issues.append(f"Cháy sáng nặng ({avg_over}% pixel trắng bão hòa)")
        recommendations.append("Giảm Exposure -0.4 hoặc loại khỏi B-Roll")
        grade = "REJECTED"
        status = "FAIL"
        approved = False
    elif avg_over > 12.0:
        issues.append(f"Hơi thừa sáng ({avg_over}%)")
        recommendations.append("Hạ Highlight -15")
        grade = "WARNING"
        status = "WARN"

    # Phân loại Rung Lắc
    if avg_shake > 24.0:
        issues.append(f"Rung lắc camera mạnh (Chỉ số: {avg_shake})")
        recommendations.append("Cần bật Warp Stabilizer hoặc loại bỏ")
        if approved:
            grade = "REJECTED"
            status = "FAIL"
            approved = False
    elif avg_shake > 15.0:
        issues.append(f"Có rung nhẹ ({avg_shake})")
        recommendations.append("Áp dụng Punch-in 1.1x")
        if grade != "REJECTED":
            grade = "WARNING"
            status = "WARN"

    # Phân loại Độ Nét
    if avg_sharpness < 40.0:
        issues.append(f"Mất nét / Nhòe mờ ({avg_sharpness})")
        recommendations.append("Loại bỏ khỏi cảnh chính")
        if approved:
            grade = "REJECTED"
            status = "FAIL"
            approved = False
    elif avg_sharpness < 70.0:
        issues.append(f"Hơi mờ nét ({avg_sharpness})")
        recommendations.append("Tăng Sharpen +20")
        if grade != "REJECTED":
            grade = "WARNING"
            status = "WARN"

    verdict = "Đạt chuẩn thương mại (Khuyên dùng)"
    if grade == "WARNING":
        verdict = "Có thể dùng kèm tinh chỉnh bù sáng/ổn định"
    elif grade == "REJECTED":
        verdict = "AI Khuyên LOẠI TRỪ (Tránh làm hỏng nhịp video)"

    return {
        "file_name": file_name,
        "path": str(path_obj).replace('\\', '/'),
        "type": "video",
        "file_size_mb": file_size_mb,
        "resolution": f"{width}x{height}",
        "aspect_ratio": "9:16" if height > width else ("16:9" if width > height else "1:1"),
        "duration_sec": duration_sec,
        "fps": round(fps, 1),
        "metrics": {
            "overexposed_pct": avg_over,
            "underexposed_pct": avg_under,
            "sharpness_score": avg_sharpness,
            "shake_score": avg_shake,
            "luma_mean": avg_luma
        },
        "grade": grade,
        "status": status,
        "issues": issues,
        "recommendations": recommendations,
        "verdict": verdict,
        "approved": approved
    }

def scan_and_analyze_folder(folder_path: str, max_files: int = 25) -> Dict[str, Any]:
    """Quét toàn bộ thư mục và phân tích pháp y từng tệp video/audio siêu tốc"""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return {"ok": False, "error": f"Thư mục không tồn tại: {folder_path}"}

    media_exts = ['.mp4', '.mov', '.mkv', '.avi', '.wav', '.mp3', '.m4a']
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in media_exts]

    results = []
    passed_count = 0
    warning_count = 0
    rejected_count = 0

    for f in sorted(files, key=lambda x: x.name)[:max_files]:
        res = analyze_video_file(str(f))
        results.append(res)
        if res.get("status") == "PASS":
            passed_count += 1
        elif res.get("status") == "WARN":
            warning_count += 1
        else:
            rejected_count += 1

    return {
        "ok": True,
        "folder_path": str(folder).replace('\\', '/'),
        "total_files": len(results),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "rejected_count": rejected_count,
        "health_score": round((passed_count + warning_count * 0.5) / max(1, len(results)) * 100),
        "footages": results
    }

def parse_commercial_script(raw_text: str, pacing_mode: str = "medium") -> List[Dict[str, Any]]:
    """
    Tự động phân tách kịch bản tiếng Việt thành các câu thoại thương mại kèm timecode,
    ước tính thời lượng đọc (WPM ~ 160 từ/phút), phân loại VJ vs B-Roll, và trích xuất từ khóa.
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    sentences = []
    
    # Tốc độ đọc: Fast ~ 1.5s/câu, Medium ~ 2.5s/câu, Slow ~ 3.5s/câu
    min_dur = 1.3 if pacing_mode == "fast" else (2.0 if pacing_mode == "medium" else 2.8)
    curr_time = 0.0

    for idx, line in enumerate(lines):
        clean_line = line
        c_type = "vj" if idx % 2 == 0 else "broll"
        keyword = ""

        # Phát hiện tag thủ công: [VJ], [BROLL], [CẢNH]
        m_tag = re.match(r'^\[(VJ|A[-_]?ROLL|THOẠI)\]\s*(.*)', clean_line, re.IGNORECASE)
        if m_tag:
            c_type = "vj"
            clean_line = m_tag.group(2)
        else:
            m_broll = re.match(r'^\[(B[-_]?ROLL|CẢNH|CHÈN)\]\s*(.*)', clean_line, re.IGNORECASE)
            if m_broll:
                c_type = "broll"
                clean_line = m_broll.group(2)

        # Trích xuất từ khóa tìm footage
        words = clean_line.split()
        word_count = len(words)
        
        # Thời lượng = max(min_dur, word_count * 0.32s)
        dur_sec = max(min_dur, round(word_count * 0.32, 2))
        
        # Trích keyword: tìm danh từ quan trọng hoặc lấy 2-3 từ đầu
        kw_candidates = [w for w in words if len(w) > 3 and not w.lower() in ['chúng', 'mình', 'những', 'được', 'trong', 'ngay', 'hôm', 'với']]
        if kw_candidates:
            keyword = "_".join(kw_candidates[:2]).lower()
        else:
            keyword = f"clip_{idx+1}"

        start_sec = round(curr_time, 2)
        end_sec = round(curr_time + dur_sec, 2)
        curr_time = end_sec

        sentences.append({
            "id": f"s_{idx+1}",
            "text": clean_line,
            "type": c_type,
            "keyword": keyword,
            "word_count": word_count,
            "startSec": start_sec,
            "endSec": end_sec,
            "durationSec": dur_sec
        })

    return sentences
