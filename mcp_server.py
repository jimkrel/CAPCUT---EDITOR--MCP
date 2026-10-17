"""
CapCut Web Studio & AI Co-Director - MCP Server (FastMCP / MCPServer)
Cung cấp các công cụ chuẩn Model Context Protocol (MCP) giao tiếp qua stdio
cho Claude Desktop, Cursor, Antigravity IDE hoặc các AI Agent khác.
"""

import sys
import json
import logging
from typing import Optional

# Cấu hình logging ra stderr để không làm bẩn luồng stdio của MCP
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MCP] %(message)s"
)

try:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("capcut-web-studio")
except ImportError:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("capcut-web-studio")

from draft_io import (
    list_projects_core,
    get_project_core,
    split_clip_core,
    update_clip_core,
    delete_clip_core,
    check_capcut_not_running,
    is_capcut_running,
    CAPCUT_DRAFT_BASE
)
from audit import (
    quality_audit_core,
    auto_fix_step_core,
    auto_fix_all_core
)
import footage_analyzer

@mcp.tool()
def list_projects() -> str:
    """Liệt kê tất cả các dự án CapCut/JianYing có trong thư mục draft của máy."""
    try:
        data = list_projects_core()
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_project(project_name: str) -> str:
    """Lấy thông tin chi tiết timeline của dự án: thời lượng, số track, danh sách segments, fps và color space."""
    try:
        data = get_project_core(project_name)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def audit_project(project_name: str) -> str:
    """Kiểm tra chất lượng video theo kịch bản: Safe Zone TikTok, Outro chết, phụ đề tràn màn hình."""
    try:
        data = quality_audit_core(project_name)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def analyze_footage_folder(folder_path: str, max_files: int = 20, profile: str = "default") -> str:
    """Phân tích thư mục footage bằng OpenCV: kiểm tra độ rung lắc, cháy sáng (overexposure), mất nét (blur)."""
    try:
        res = footage_analyzer.scan_and_analyze_folder(folder_path, max_files=max_files, profile=profile)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def split_clip(project_name: str, target_segment_id: str, split_us: int) -> str:
    """Cắt clip tại một điểm thời gian cụ thể (microgiây - us). Cần đóng CapCut trước khi thực hiện."""
    if is_capcut_running():
        return json.dumps({
            "status": "error",
            "code": 409,
            "message": "CapCut Desktop đang chạy! Vui lòng đóng ứng dụng CapCut trước khi cắt clip."
        }, ensure_ascii=False)
    try:
        check_capcut_not_running()
        res = split_clip_core(project_name, target_segment_id, split_us)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def update_clip(
    project_name: str,
    target_segment_id: str,
    start_us: Optional[int] = None,
    duration_us: Optional[int] = None,
    speed: Optional[float] = None
) -> str:
    """Cập nhật thời gian bắt đầu, thời lượng hoặc tốc độ (speed) của clip trên timeline. Cần đóng CapCut."""
    if is_capcut_running():
        return json.dumps({
            "status": "error",
            "code": 409,
            "message": "CapCut Desktop đang chạy! Vui lòng đóng ứng dụng CapCut trước khi cập nhật clip."
        }, ensure_ascii=False)
    try:
        check_capcut_not_running()
        res = update_clip_core(
            project_name,
            target_segment_id,
            start_us=start_us,
            duration_us=duration_us,
            speed=speed
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def delete_clip(project_name: str, target_segment_id: str) -> str:
    """Xóa clip khỏi timeline và dọn dẹp materials mồ côi. Cần đóng CapCut trước khi thực hiện."""
    if is_capcut_running():
        return json.dumps({
            "status": "error",
            "code": 409,
            "message": "CapCut Desktop đang chạy! Vui lòng đóng ứng dụng CapCut trước khi xóa clip."
        }, ensure_ascii=False)
    try:
        check_capcut_not_running()
        res = delete_clip_core(project_name, target_segment_id)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@mcp.tool()
def auto_fix(project_name: str, error_id: Optional[str] = None) -> str:
    """Tự động sửa lỗi kịch bản: Safe Zone TikTok, Outro chết, Letterbox viền đen, Montserrat Shadow.
    Nếu không truyền error_id, hệ thống sẽ tự động sửa toàn bộ (auto-fix all).
    Cần đóng CapCut trước khi thực hiện."""
    if is_capcut_running():
        return json.dumps({
            "status": "error",
            "code": 409,
            "message": "CapCut Desktop đang chạy! Vui lòng đóng ứng dụng CapCut trước khi thực hiện auto-fix."
        }, ensure_ascii=False)
    try:
        check_capcut_not_running()
        if error_id:
            res = auto_fix_step_core(project_name, error_id)
        else:
            res = auto_fix_all_core(project_name)
        return json.dumps(res, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

if __name__ == "__main__":
    logging.info(f"Đang khởi chạy CapCut Web Studio MCP Server (Draft Base: {CAPCUT_DRAFT_BASE})...")
    mcp.run(transport="stdio")
