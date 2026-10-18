import re
from pathlib import Path
from typing import Dict, List, Any

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# Bảng ngưỡng phân tích pháp y footage
THRESHOLDS = {
    "default": {
        "overexposed_pixel": 250,
        "overexposed_std": 3.0,        # std thấp biểu thị vùng cháy sáng bệt, hoàn toàn mất chi tiết
        "overexposed_warn_pct": 12.0,
        "overexposed_reject_pct": 25.0,
        "underexposed_pixel": 25,
        "underexposed_warn_pct": 30.0,
        "sharpness_warn": 50.0,
        "sharpness_reject": 25.0,
        "texture_min_std": 6.0,        # Ngưỡng tối thiểu để xác định cảnh có chi tiết/texture
        "shake_warn": 8.0,
        "shake_reject": 16.0
    },
    "white_bg": {
        "overexposed_pixel": 252,
        "overexposed_std": 2.0,
        "overexposed_warn_pct": 35.0,  # Nền trắng studio cho phép tỷ lệ trắng sáng cao
        "overexposed_reject_pct": 55.0,
        "underexposed_pixel": 25,
        "underexposed_warn_pct": 30.0,
        "sharpness_warn": 50.0,
        "sharpness_reject": 25.0,
        "texture_min_std": 6.0,
        "shake_warn": 8.0,
        "shake_reject": 16.0
    }
}

def analyze_video_file(file_path: str, max_samples: int = 12, profile: str = "default") -> Dict[str, Any]:
    """
    Phân tích pháp y chất lượng footage bằng Computer Vision:
    1. Độ sáng: Tỷ lệ cháy sáng (pixel >= 250 và mất chi tiết std <= 3.0), thiếu sáng (<25), Luma trung bình.
    2. Độ ổn định: Ước lượng dịch chuyển toàn cục của camera bằng cv2.phaseCorrelate.
    3. Độ sắc nét: Laplacian variance trên top 20% block có tương phản cao nhất.
    4. Trải đều 12 mẫu trên toàn clip.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        return {"ok": False, "error": f"Tệp không tồn tại: {file_path}"}

    file_name = path_obj.name
    file_size_mb = round(path_obj.stat().st_size / (1024 * 1024), 2)
    ext = path_obj.suffix.lower()

    # 3.5: Xử lý Audio thuần túy: trả metrics null, grade "N/A", status "N/A"
    if ext in ['.wav', '.mp3', '.m4a']:
        return {
            "ok": True,
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "audio",
            "file_size_mb": file_size_mb,
            "duration_sec": 0.0,
            "resolution": None,
            "aspect_ratio": None,
            "metrics": None,
            "grade": "N/A",
            "status": "N/A",
            "issues": [],
            "recommendations": ["Tệp âm thanh"],
            "verdict": "Tệp âm thanh",
            "approved": True
        }

    # 3.5: Không có OpenCV thì trả ok: false kèm lỗi
    if not HAS_CV2:
        return {
            "ok": False,
            "error": "OpenCV (cv2) chưa được cài đặt trên hệ thống",
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "video"
        }

    cfg = THRESHOLDS.get(profile, THRESHOLDS["default"])

    cap = cv2.VideoCapture(str(path_obj))
    if not cap.isOpened():
        return {
            "ok": False,
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "video",
            "file_size_mb": file_size_mb,
            "resolution": "--",
            "aspect_ratio": "--",
            "metrics": None,
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

    if total_frames <= 0:
        cap.release()
        return {
            "ok": False,
            "error": "Không thể xác định số khung hình video",
            "file_name": file_name,
            "path": str(path_obj).replace('\\', '/'),
            "type": "video"
        }

    # 3.1: Lấy ~12 mẫu trải đều toàn clip bằng cap.set(cv2.CAP_PROP_POS_FRAMES, i)
    sample_count = min(max_samples, total_frames)
    if total_frames <= 1:
        indices = [0]
    elif total_frames <= sample_count:
        indices = list(range(total_frames))
    else:
        # Chừa frame cuối để có cặp kế tiếp đo rung
        max_idx = total_frames - 2 if total_frames > 2 else total_frames - 1
        step = max_idx / max(1, sample_count - 1)
        indices = [int(i * step) for i in range(sample_count)]

    overexposed_list = []
    underexposed_list = []
    sharpness_list = []
    shake_diffs = []
    luma_means = []
    low_texture_count = 0

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        if w > 320:
            scale = 320.0 / w
            small_frame = cv2.resize(frame, (320, int(h * scale)))
        else:
            small_frame = frame

        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        gh, gw = gray.shape
        luma_mean = float(np.mean(gray))
        luma_means.append(luma_mean)

        # 3.4: Cháy sáng: chỉ coi là cháy khi pixel >= threshold VÀ vùng đó mất chi tiết (độ lệch chuẩn thấp)
        # Chia thành các block 16x16 để kiểm tra vùng bão hòa mất chi tiết
        block_size = 16
        blown_blocks = 0
        total_blocks = 0
        
        for by in range(0, gh - block_size + 1, block_size):
            for bx in range(0, gw - block_size + 1, block_size):
                blk = gray[by:by + block_size, bx:bx + block_size]
                b_mean = float(np.mean(blk))
                b_std = float(np.std(blk))
                if b_mean >= cfg["overexposed_pixel"] and b_std <= cfg["overexposed_std"]:
                    blown_blocks += 1
                total_blocks += 1
                
        over_pct = (blown_blocks / max(1, total_blocks)) * 100.0
        under_pct = float(np.mean(gray < cfg["underexposed_pixel"]) * 100.0)
        overexposed_list.append(over_pct)
        underexposed_list.append(under_pct)

        # 3.3: Độ nét: tính trên vùng có cạnh (top ~20% block có tương phản cao nhất)
        sh_block_size = 32
        stds = []
        laps = []
        for by in range(0, gh - sh_block_size + 1, sh_block_size):
            for bx in range(0, gw - sh_block_size + 1, sh_block_size):
                blk = gray[by:by + sh_block_size, bx:bx + sh_block_size]
                b_std = float(np.std(blk))
                b_lap = float(cv2.Laplacian(blk, cv2.CV_64F).var())
                stds.append(b_std)
                laps.append(b_lap)

        if stds:
            # Sắp xếp theo std giảm dần
            sorted_pairs = sorted(zip(stds, laps), key=lambda x: x[0], reverse=True)
            k = max(1, int(len(sorted_pairs) * 0.2))
            top_pairs = sorted_pairs[:k]
            mean_contrast = float(np.mean([p[0] for p in top_pairs]))
            
            # Nếu cảnh quá ít texture (trời mượt, tường phẳng) thì không kết luận mất nét
            if mean_contrast < cfg["texture_min_std"]:
                low_texture_count += 1
            else:
                top_lap_var = float(np.mean([p[1] for p in top_pairs]))
                sharpness_list.append(top_lap_var)
        else:
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            sharpness_list.append(lap_var)

        # 3.2: Rung lắc: Ước lượng dịch chuyển toàn cục của camera bằng cv2.phaseCorrelate trên 2 frame liền kề
        if idx + 1 < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx + 1)
            ret2, frame2 = cap.read()
            if ret2 and frame2 is not None:
                if frame2.shape[1] > 320:
                    scale2 = 320.0 / frame2.shape[1]
                    small_frame2 = cv2.resize(frame2, (320, int(frame2.shape[0] * scale2)))
                else:
                    small_frame2 = frame2
                gray2 = cv2.cvtColor(small_frame2, cv2.COLOR_BGR2GRAY)
                
                # Áp dụng Hanning window để giảm mép biên giả lập khi tương quan pha
                try:
                    hann = cv2.createHanningWindow((gw, gh), cv2.CV_32F)
                    g1_f = gray.astype(np.float32)
                    g2_f = gray2.astype(np.float32)
                    (dx, dy), response = cv2.phaseCorrelate(g1_f, g2_f, hann)
                    shift = float(np.sqrt(dx**2 + dy**2))
                    shake_diffs.append(shift)
                except Exception:
                    pass

    cap.release()

    avg_over = round(float(np.mean(overexposed_list)), 1) if overexposed_list else 0.0
    avg_under = round(float(np.mean(underexposed_list)), 1) if underexposed_list else 0.0
    avg_shake = round(float(np.mean(shake_diffs)), 1) if shake_diffs else 0.0
    avg_luma = round(float(np.mean(luma_means)), 1) if luma_means else 128.0

    # Xử lý độ nét và tình trạng thiếu texture
    is_texture_insufficient = (low_texture_count > len(indices) * 0.7)
    if sharpness_list:
        avg_sharpness = round(float(np.mean(sharpness_list)), 1)
    else:
        avg_sharpness = None

    issues = []
    recommendations = []
    grade = "EXCELLENT"
    status = "PASS"
    approved = True

    # Phân loại Cháy Sáng
    if avg_over > cfg["overexposed_reject_pct"]:
        issues.append(f"Cháy sáng nặng ({avg_over}% pixel trắng bão hòa mất chi tiết)")
        recommendations.append("Giảm Exposure hoặc loại khỏi B-Roll")
        grade = "REJECTED"
        status = "FAIL"
        approved = False
    elif avg_over > cfg["overexposed_warn_pct"]:
        issues.append(f"Hơi thừa sáng ({avg_over}%)")
        recommendations.append("Hạ Highlight")
        grade = "WARNING"
        status = "WARN"

    # Phân loại Rung Lắc toàn cục
    if avg_shake > cfg["shake_reject"]:
        issues.append(f"Rung lắc camera mạnh (Chỉ số dịch chuyển: {avg_shake:.1f})")
        recommendations.append("Cần bật Warp Stabilizer hoặc loại bỏ")
        grade = "REJECTED"
        status = "FAIL"
        approved = False
    elif avg_shake > cfg["shake_warn"]:
        issues.append(f"Có rung nhẹ ({avg_shake:.1f})")
        recommendations.append("Áp dụng Punch-in 1.1x")
        if grade != "REJECTED":
            grade = "WARNING"
            status = "WARN"

    # Phân loại Độ Nét
    if is_texture_insufficient:
        # Không đủ texture để kết luận mất nét, không báo lỗi
        recommendations.append("Cảnh đồng nhất ít chi tiết, không phát hiện mất nét")
    elif avg_sharpness is not None:
        if avg_sharpness < cfg["sharpness_reject"]:
            issues.append(f"Mất nét / Nhòe mờ ({avg_sharpness})")
            recommendations.append("Loại bỏ khỏi cảnh chính")
            grade = "REJECTED"
            status = "FAIL"
            approved = False
        elif avg_sharpness < cfg["sharpness_warn"]:
            issues.append(f"Hơi mờ nét ({avg_sharpness})")
            recommendations.append("Tăng Sharpen +15")
            if grade != "REJECTED":
                grade = "WARNING"
                status = "WARN"

    verdict = "Đạt chuẩn thương mại (Khuyên dùng)"
    if grade == "WARNING":
        verdict = "Có thể dùng kèm tinh chỉnh bù sáng/ổn định"
    elif grade == "REJECTED":
        verdict = "AI Khuyên LOẠI TRỪ (Tránh làm hỏng nhịp video)"

    return {
        "ok": True,
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
            "luma_mean": avg_luma,
            "insufficient_texture": is_texture_insufficient
        },
        "grade": grade,
        "status": status,
        "issues": issues,
        "recommendations": recommendations,
        "verdict": verdict,
        "approved": approved
    }

def scan_and_analyze_folder(folder_path: str, max_files: int = 25, profile: str = "default") -> Dict[str, Any]:
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
        res = analyze_video_file(str(f), profile=profile)
        results.append(res)
        if res.get("status") == "PASS":
            passed_count += 1
        elif res.get("status") == "WARN":
            warning_count += 1
        elif res.get("status") == "FAIL":
            rejected_count += 1

    summary = {
        "total_scanned": len(results),
        "approved_count": passed_count,
        "warning_count": warning_count,
        "rejected_count": rejected_count,
        "health_score": round((passed_count + warning_count * 0.5) / max(1, len(results)) * 100)
    }

    proposals = []
    if rejected_count > 0:
        proposals.append(f"AI đề xuất loại trừ {rejected_count} clip bị rung lắc hoặc cháy sáng khỏi bể B-Roll để đảm bảo nhịp dựng.")
    if warning_count > 0:
        proposals.append(f"Đề xuất áp dụng Punch-in Zoom 1.15x hoặc hạ Highlight cho {warning_count} clip có cảnh báo nhẹ.")
    if not proposals:
        proposals.append("Toàn bộ footage đạt chuẩn thương mại cao, sẵn sàng biên dịch 13 lớp CapCut.")

    return {
        "status": "success",
        "ok": True,
        "summary": summary,
        "proposals": proposals,
        "files": results,
        "folder_path": str(folder).replace('\\', '/'),
        "total_files": len(results),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "rejected_count": rejected_count,
        "health_score": summary["health_score"],
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
    
    # Tốc độ đọc: Hỗ trợ cả preset ("fast", "medium", "slow") và số giây điền tự do ("1.5s", "2.8", "3.0")
    min_dur = 2.0
    p_str = str(pacing_mode).strip().lower() if pacing_mode else "medium"
    if p_str == "fast":
        min_dur = 1.3
    elif p_str == "medium":
        min_dur = 2.0
    elif p_str == "slow":
        min_dur = 2.8
    else:
        m_num = re.search(r'(\d+(\.\d+)?)', p_str)
        if m_num:
            try:
                min_dur = max(0.5, min(15.0, float(m_num.group(1))))
            except Exception:
                min_dur = 2.0
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
            "durationSec": dur_sec,
            "durationUs": int(round(dur_sec * 1e6))
        })

    return sentences
