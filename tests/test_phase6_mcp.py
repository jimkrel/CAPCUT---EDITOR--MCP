import json
import pytest
from pathlib import Path
from unittest.mock import patch

import mcp_server
import draft_io

@pytest.fixture
def mock_draft_env(tmp_path, monkeypatch):
    draft_base = tmp_path / "com.lveditor.draft"
    draft_base.mkdir(parents=True)
    monkeypatch.setattr(draft_io, "CAPCUT_DRAFT_BASE", draft_base)
    monkeypatch.setattr(mcp_server, "CAPCUT_DRAFT_BASE", draft_base)
    
    # Tạo dự án mẫu
    proj_dir = draft_base / "Test_MCP_Project"
    proj_dir.mkdir()
    
    sample_draft = {
        "duration": 5000000,
        "fps": 30.0,
        "materials": {
            "videos": [{"id": "vid_1", "path": "test.mp4", "duration": 5000000}],
            "texts": [
                {
                    "id": "txt_1",
                    "content": json.dumps({"text": "Tiêu đề video mẫu", "styles": []})
                }
            ],
            "speeds": []
        },
        "tracks": [
            {
                "id": "tr_v1",
                "type": "video",
                "segments": [
                    {
                        "id": "seg_v1",
                        "material_id": "vid_1",
                        "target_timerange": {"start": 0, "duration": 5000000},
                        "source_timerange": {"start": 0, "duration": 5000000},
                        "clip": {"scale": {"x": 1.0, "y": 1.0}}
                    }
                ]
            },
            {
                "id": "tr_t1",
                "type": "text",
                "segments": [
                    {
                        "id": "seg_t1",
                        "material_id": "txt_1",
                        "target_timerange": {"start": 0, "duration": 2000000},
                        "clip": {"transform": {"y": -0.60}} # Lỗi vi phạm safe zone
                    }
                ]
            }
        ]
    }
    
    draft_file = proj_dir / "draft_content.json"
    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(sample_draft, f, indent=2)
        
    return draft_base, "Test_MCP_Project"

def test_mcp_list_projects(mock_draft_env):
    draft_base, proj_name = mock_draft_env
    res_str = mcp_server.list_projects()
    res = json.loads(res_str)
    assert "projects" in res
    names = [p["name"] for p in res.get("projects", [])]
    assert proj_name in names

def test_mcp_get_project(mock_draft_env):
    draft_base, proj_name = mock_draft_env
    res_str = mcp_server.get_project(proj_name)
    res = json.loads(res_str)
    assert res.get("project_name") == proj_name
    assert res.get("duration_us") == 5000000
    assert len(res.get("tracks", [])) == 2

def test_mcp_audit_project(mock_draft_env):
    draft_base, proj_name = mock_draft_env
    res_str = mcp_server.audit_project(proj_name)
    res = json.loads(res_str)
    assert res.get("project_name") == proj_name
    # Phải bắt được lỗi SAFE_ZONE_VIOLATION do y = -0.60
    issue_types = [i["type"] for i in res.get("issues", [])]
    assert "SAFE_ZONE_VIOLATION" in issue_types

def test_mcp_auto_fix_and_split_clip(mock_draft_env):
    draft_base, proj_name = mock_draft_env
    
    # 1. Test auto-fix
    fix_res_str = mcp_server.auto_fix(proj_name)
    fix_res = json.loads(fix_res_str)
    assert fix_res.get("status") == "success"
    
    # Kiểm tra sau khi auto-fix, toạ độ y đã về -0.404
    draft_file = draft_base / proj_name / "draft_content.json"
    with open(draft_file, "r", encoding="utf-8") as f:
        d = json.load(f)
    text_seg = d["tracks"][1]["segments"][0]
    assert text_seg["clip"]["transform"]["y"] == -0.404
    
    # 2. Test split_clip
    split_res_str = mcp_server.split_clip(proj_name, "seg_v1", 2000000)
    split_res = json.loads(split_res_str)
    assert split_res.get("status") == "success"
    
    # Kiểm tra track video đã có 2 segment
    with open(draft_file, "r", encoding="utf-8") as f:
        d2 = json.load(f)
    assert len(d2["tracks"][0]["segments"]) == 2

def test_mcp_capcut_running_blocks_modifications(mock_draft_env):
    draft_base, proj_name = mock_draft_env
    
    with patch("mcp_server.is_capcut_running", return_value=True):
        res_split = json.loads(mcp_server.split_clip(proj_name, "seg_v1", 1000000))
        assert res_split.get("code") == 409
        
        res_del = json.loads(mcp_server.delete_clip(proj_name, "seg_v1"))
        assert res_del.get("code") == 409
        
        res_fix = json.loads(mcp_server.auto_fix(proj_name))
        assert res_fix.get("code") == 409
