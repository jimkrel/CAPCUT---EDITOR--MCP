import pytest
import json
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from server import app, CAPCUT_DRAFT_BASE

client = TestClient(app)

@pytest.fixture
def mock_draft_with_null_clip(tmp_path):
    # Tạo dự án mock có "clip": null và segment audio/effect
    proj_dir = tmp_path / "TestNullClipProj"
    proj_dir.mkdir(parents=True)
    draft_file = proj_dir / "draft_content.json"
    
    draft_data = {
        "duration": 5000000,
        "fps": 30,
        "tracks": [
            {
                "id": "track_audio_1",
                "type": "audio",
                "flag": 0,
                "segments": [
                    {
                        "id": "seg_audio_null",
                        "material_id": "mat_audio_1",
                        "target_timerange": {"start": 0, "duration": 3000000},
                        "clip": None, # Clip là null
                        "extra_material_refs": []
                    }
                ]
            },
            {
                "id": "track_video_1",
                "type": "video",
                "flag": 0,
                "segments": [
                    {
                        "id": "seg_video_1",
                        "material_id": "mat_video_1",
                        "target_timerange": {"start": 0, "duration": 4000000},
                        "source_timerange": {"start": 0, "duration": 4000000},
                        "speed": 1.0,
                        "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0, "y": 0}},
                        "extra_material_refs": ["effect_ref_1"],
                        "keyframe_list": [
                            {"id": "kf_1", "time_offset": 500000},
                            {"id": "kf_2", "time_offset": 2500000}
                        ]
                    }
                ]
            }
        ],
        "materials": {
            "videos": [{"id": "mat_video_1", "path": "test.mp4", "duration": 4000000}],
            "audios": [{"id": "mat_audio_1", "name": "voiceover.mp3", "duration": 3000000}],
            "texts": [],
            "video_effects": [
                {"id": "effect_ref_1", "name": "GlowEffect", "effect_id": "glow_123"}
            ],
            "material_animations": [],
            "speeds": [],
            "transitions": [],
            "stickers": []
        }
    }
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, ensure_ascii=False)
        
    with patch("server.CAPCUT_DRAFT_BASE", tmp_path):
        yield "TestNullClipProj", draft_file

def test_get_project_with_null_clip_no_err(mock_draft_with_null_clip):
    proj_name, _ = mock_draft_with_null_clip
    res = client.get(f"/api/project/{proj_name}")
    assert res.status_code == 200
    data = res.json()
    
    # Kiểm tra không có [ERR] trong bất kỳ label nào
    for track in data["tracks"]:
        for seg in track["segments"]:
            assert "[ERR]" not in seg["label"]
            assert seg["end_us"] > 0
            
    # Audio segment phải có label "Audio" hoặc tên audio, không được đỏ sẫm lỗi
    audio_seg = data["tracks"][0]["segments"][0]
    assert audio_seg["label"] == "voiceover.mp3"
    assert audio_seg["end_us"] == 3000000

def test_capcut_running_blocks_write_with_409(mock_draft_with_null_clip):
    proj_name, _ = mock_draft_with_null_clip
    with patch("server.is_capcut_running", return_value=True):
        res = client.post("/api/update-clip", json={
            "project_name": proj_name,
            "segment_id": "seg_video_1",
            "scale": 1.2
        })
        assert res.status_code == 409
        assert "CapCut Desktop đang chạy" in res.json()["detail"]

def test_split_clip_clones_material_and_splits_keyframes(mock_draft_with_null_clip):
    proj_name, draft_file = mock_draft_with_null_clip
    with patch("server.is_capcut_running", return_value=False):
        res = client.post("/api/split-clip", json={
            "project_name": proj_name,
            "command": "split",
            "target_segment_id": "seg_video_1",
            "playhead_time_us": 2000000
        })
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        
        # Đọc lại draft
        with open(draft_file, "r", encoding="utf-8") as f:
            updated = json.load(f)
            
        video_track = updated["tracks"][1]
        assert len(video_track["segments"]) == 2
        seg1 = video_track["segments"][0]
        seg2 = video_track["segments"][1]
        
        # Kiểm tra extra_material_refs được clone ID mới
        assert seg1["extra_material_refs"][0] != seg2["extra_material_refs"][0]
        effects = updated["materials"]["video_effects"]
        assert len(effects) == 2
        
        # Kiểm tra keyframes được chia lại theo thời gian cắt
        assert len(seg1["keyframe_list"]) == 1
        assert seg1["keyframe_list"][0]["time_offset"] == 500000
        assert len(seg2["keyframe_list"]) == 1
        assert seg2["keyframe_list"][0]["time_offset"] == 500000  # 2500000 - 2000000

def test_undo_and_redo_flow(mock_draft_with_null_clip):
    proj_name, draft_file = mock_draft_with_null_clip
    with patch("server.is_capcut_running", return_value=False):
        # 1. Update scale
        client.post("/api/update-clip", json={
            "project_name": proj_name,
            "segment_id": "seg_video_1",
            "scale": 1.5
        })
        with open(draft_file, "r", encoding="utf-8") as f:
            d = json.load(f)
        assert d["tracks"][1]["segments"][0]["clip"]["scale"]["x"] == 1.5
        
        # 2. Undo
        undo_res = client.post(f"/api/undo/{proj_name}")
        assert undo_res.status_code == 200
        assert undo_res.json()["status"] == "success"
        with open(draft_file, "r", encoding="utf-8") as f:
            d_undone = json.load(f)
        assert d_undone["tracks"][1]["segments"][0]["clip"]["scale"]["x"] == 1.0
        
        # 3. Redo
        redo_res = client.post(f"/api/redo/{proj_name}")
        assert redo_res.status_code == 200
        assert redo_res.json()["status"] == "success"
        with open(draft_file, "r", encoding="utf-8") as f:
            d_redone = json.load(f)
        assert d_redone["tracks"][1]["segments"][0]["clip"]["scale"]["x"] == 1.5

def test_mcp_tools_disconnected_when_script_missing():
    with patch.dict("os.environ", {"CAPCUT_MCP_JS": "non_existent_script.js"}):
        res = client.get("/api/mcp/tools")
        assert res.status_code == 200
        assert res.json()["status"] == "disconnected"
