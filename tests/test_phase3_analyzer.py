import pytest
import cv2
import numpy as np
from pathlib import Path
from unittest.mock import patch
import footage_analyzer

def create_synthetic_video(file_path: Path, frames: list, fps: int = 10):
    h, w, c = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (w, h))
    for f in frames:
        out.write(f)
    out.release()

@pytest.fixture
def temp_video_dir(tmp_path):
    d = tmp_path / "synthetic_videos"
    d.mkdir(parents=True)
    return d

def test_case_a_2s_normal_8s_white_blown(temp_video_dir):
    # (a) 2 giây bình thường rồi 8 giây trắng xóa (fps = 10: 20 frame bình thường, 80 frame trắng xóa 255)
    # Kỳ vọng: Quét toàn bộ clip trải đều 12 frame sẽ phát hiện cháy sáng nặng -> KHÔNG được EXCELLENT (phải là REJECTED hoặc WARNING)
    frames = []
    w, h = 320, 240
    for _ in range(20):
        # Frame bình thường với độ sáng trung bình ~120
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        # Thêm texture
        f[50:150, 50:200] = np.random.randint(50, 180, (100, 150, 3), dtype=np.uint8)
        frames.append(f)
    for _ in range(80):
        # 8 giây trắng xóa hoàn toàn mất chi tiết
        f = np.full((h, w, 3), 255, dtype=np.uint8)
        frames.append(f)
        
    vid_path = temp_video_dir / "case_a_blown.mp4"
    create_synthetic_video(vid_path, frames, fps=10)
    
    res = footage_analyzer.analyze_video_file(str(vid_path))
    assert res["ok"] is True
    assert res["grade"] != "EXCELLENT"
    assert res["status"] in ["FAIL", "WARN"]
    assert res["metrics"]["overexposed_pct"] > 12.0

def test_case_b_white_bg_with_textured_object(temp_video_dir):
    # (b) Nền trắng studio + vật thể có texture rõ ràng, camera tĩnh
    # Kỳ vọng: Với profile white_bg, clip được PASS (không bị REJECTED vì nền trắng)
    frames = []
    w, h = 320, 240
    for _ in range(40):
        f = np.full((h, w, 3), 253, dtype=np.uint8)
        # Vật thể ở giữa có chi tiết phong phú
        cv2.rectangle(f, (80, 40), (240, 200), (40, 50, 60), -1)
        cv2.putText(f, "PRODUCT", (90, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        frames.append(f)
        
    vid_path = temp_video_dir / "case_b_white_bg.mp4"
    create_synthetic_video(vid_path, frames, fps=10)
    
    res = footage_analyzer.analyze_video_file(str(vid_path), profile="white_bg")
    assert res["ok"] is True
    assert res["status"] == "PASS"
    assert res["approved"] is True

def test_case_c_smooth_gradient_no_blur_issue(temp_video_dir):
    # (c) Gradient mượt (cảnh trơn ít texture như trời hoàng hôn / tường phẳng)
    # Kỳ vọng: Không bị báo issue "mất nét" sai, không kết luận nhòe mờ
    frames = []
    w, h = 320, 240
    # Tạo gradient mượt theo chiều dọc
    grad = np.tile(np.linspace(100, 200, h, dtype=np.uint8)[:, None], (1, w))
    grad_bgr = cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR)
    for _ in range(30):
        frames.append(grad_bgr)
        
    vid_path = temp_video_dir / "case_c_gradient.mp4"
    create_synthetic_video(vid_path, frames, fps=10)
    
    res = footage_analyzer.analyze_video_file(str(vid_path))
    assert res["ok"] is True
    # Đảm bảo không có issue mất nét
    blur_issues = [iss for iss in res["issues"] if "Mất nét" in iss or "mờ nét" in iss]
    assert len(blur_issues) == 0

def test_case_d_static_camera_moving_object_low_shake(temp_video_dir):
    # (d) Camera tĩnh, vật thể chạy ngang qua khung hình
    # Kỳ vọng: phaseCorrelate camera toàn cục bắt nền tĩnh -> shake_score thấp, không bị WARNING rung lắc
    frames = []
    w, h = 320, 240
    for i in range(40):
        # Nền cố định có texture
        f = np.full((h, w, 3), 100, dtype=np.uint8)
        cv2.circle(f, (50, 50), 30, (180, 180, 180), -1)
        cv2.rectangle(f, (20, 150), (100, 220), (150, 120, 80), -1)
        cv2.rectangle(f, (220, 40), (300, 180), (80, 140, 160), -1)
        
        # Vật thể nhỏ di chuyển ngang từ trái sang phải
        obj_x = int(10 + i * 6)
        cv2.circle(f, (obj_x, 120), 15, (0, 0, 255), -1)
        frames.append(f)
        
    vid_path = temp_video_dir / "case_d_moving_object.mp4"
    create_synthetic_video(vid_path, frames, fps=10)
    
    res = footage_analyzer.analyze_video_file(str(vid_path))
    assert res["ok"] is True
    assert res["metrics"]["shake_score"] < 8.0
    shake_issues = [iss for iss in res["issues"] if "Rung lắc" in iss or "rung" in iss]
    assert len(shake_issues) == 0

def test_audio_file_returns_na(tmp_path):
    # File audio phải trả metrics null, status "N/A"
    audio_file = tmp_path / "sample.mp3"
    audio_file.write_bytes(b"dummy audio content")
    
    res = footage_analyzer.analyze_video_file(str(audio_file))
    assert res["ok"] is True
    assert res["type"] == "audio"
    assert res["metrics"] is None
    assert res["status"] == "N/A"
    assert res["grade"] == "N/A"

def test_missing_opencv_returns_error(tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"dummy video")
    with patch("footage_analyzer.HAS_CV2", False):
        res = footage_analyzer.analyze_video_file(str(test_file))
        assert res["ok"] is False
        assert "chưa được cài đặt" in res["error"]
