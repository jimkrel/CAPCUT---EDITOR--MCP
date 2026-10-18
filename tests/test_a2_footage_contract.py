import cv2
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def create_synthetic_clip(file_path: Path, frames_count: int = 20):
    w, h = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(file_path), fourcc, 10, (w, h))
    for _ in range(frames_count):
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        f[40:160, 40:200] = np.random.randint(40, 180, (120, 160, 3), dtype=np.uint8)
        out.write(f)
    out.release()

def test_a2_footage_analysis_contract(tmp_path):
    # Tạo thư mục test có 1 video
    test_folder = tmp_path / "mock_broll"
    test_folder.mkdir(parents=True)
    vid_file = test_folder / "clip_01.mp4"
    create_synthetic_clip(vid_file, 20)
    
    resp = client.post(
        "/api/ai-agent/analyze-footage-folder",
        json={"folder_path": str(test_folder)},
        headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    
    # Assert đủ các khóa theo hợp đồng
    assert data.get("status") == "success"
    assert data.get("ok") is True
    assert "summary" in data
    assert "proposals" in data
    assert "files" in data
    
    summary = data["summary"]
    assert "total_scanned" in summary
    assert "approved_count" in summary
    assert "warning_count" in summary
    assert "rejected_count" in summary
    assert "health_score" in summary
    assert summary["total_scanned"] == 1
    
    assert len(data["files"]) == 1
    f0 = data["files"][0]
    required_file_fields = [
        "file_name", "path", "resolution", "metrics",
        "grade", "status", "issues", "recommendations",
        "verdict", "approved"
    ]
    for field in required_file_fields:
        assert field in f0, f"Field '{field}' missing from files element"
