from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_1_1_mcp_call_tool_whitelist_rejection():
    """Tên tool lạ hoặc có dấu nháy / chèn mã phải bị trả 400"""
    bad_payloads = [
        {"toolName": "malicious_tool'; process.exit(1); '", "arguments": {}},
        {"toolName": "random_fake_tool", "arguments": {}},
        {"toolName": "../../../etc/passwd", "arguments": {}},
    ]
    for p in bad_payloads:
        resp = client.post("/api/mcp/call-tool", json=p, headers={"Origin": "http://127.0.0.1:8765"})
        assert resp.status_code == 400, f"Expected 400 for {p['toolName']}, got {resp.status_code}: {resp.text}"

def test_1_2_cors_origin_post_validation():
    """Request POST có Origin không nằm trong whitelist phải bị từ chối 403"""
    # Origin lạ -> 403
    resp_bad = client.post(
        "/api/mcp/call-tool",
        json={"toolName": "capcut_safe_launch", "arguments": {}},
        headers={"Origin": "http://evil-attacker.com"}
    )
    assert resp_bad.status_code == 403, f"Expected 403 for untrusted origin, got {resp_bad.status_code}"

    # Origin hợp lệ -> không bị 403
    resp_good = client.post(
        "/api/mcp/call-tool",
        json={"toolName": "capcut_safe_launch", "arguments": {}},
        headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert resp_good.status_code != 403

def test_1_3_media_endpoint_path_and_extension_restriction(tmp_path):
    """/api/media chỉ cho phép file media hợp lệ trong thư mục dự án"""
    # Đuôi file bị cấm -> 403
    bad_ext_file = tmp_path / "notepad.exe"
    resp_exe = client.get(f"/api/media?path={bad_ext_file.resolve()}")
    assert resp_exe.status_code == 403

    # File không thuộc đuôi media cho phép -> 403
    bad_txt_file = tmp_path / "hosts.txt"
    resp_hosts = client.get(f"/api/media?path={bad_txt_file.resolve()}")
    assert resp_hosts.status_code == 403

    # File không tồn tại nhưng đuôi mp4 trong thư mục lạ ngoài draft -> 403
    outside_mp4 = tmp_path / "fake_unknown_dir" / "video.mp4"
    resp_fake = client.get(f"/api/media?path={outside_mp4.resolve()}")
    assert resp_fake.status_code == 403

def test_1_4_project_name_path_traversal():
    """Tên project chứa path traversal hoặc ký tự lạ phải bị từ chối 400 hoặc 403"""
    traversal_names = [
        "../test_project",
        "../../Windows/System32",
        "project/../sub",
        "bad;project",
        "bad|name"
    ]
    for name in traversal_names:
        resp = client.get(f"/api/project/{name}")
        assert resp.status_code in [400, 403, 404], f"Expected 400 or 403 for {name}, got {resp.status_code}"

def test_1_4_footage_folder_forbidden_path():
    """Thư mục footage trỏ vào thư mục hệ thống phải bị từ chối 403"""
    resp_win = client.post(
        "/api/ai-agent/analyze-footage-folder",
        json={"folder_path": "C:\\Windows"},
        headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert resp_win.status_code in [400, 403]
