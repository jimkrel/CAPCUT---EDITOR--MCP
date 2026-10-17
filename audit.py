import os
import json
from pathlib import Path
from typing import Dict, Any

from draft_io import (
    get_draft_file,
    check_capcut_not_running,
    save_draft_with_history,
    recalculate_project_duration,
    resolve_draft_path
)

def get_montserrat_font_path() -> str:
    env_font = os.environ.get("MONTSERRAT_FONT_PATH")
    if env_font and Path(env_font).exists():
        return str(Path(env_font)).replace('\\', '/')
    user_font = Path.home() / "AppData/Local/Microsoft/Windows/Fonts/Montserrat-Regular.otf"
    if user_font.exists():
        return str(user_font).replace('\\', '/')
    return "Montserrat-Regular.otf"


def quality_audit_core(project_name: str) -> Dict[str, Any]:
    """Kiểm tra chất lượng tổng quát dự án CapCut (Safe zone, độ dài phụ đề, outro chết)."""
    draft_file = get_draft_file(project_name)
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    issues = []
    score = 100
    
    # 1. Audit Safe Zone
    unsafe_texts = 0
    texts = (data.get("materials") or {}).get("texts", [])
    for track in data.get("tracks", []):
        if track.get("type") == "text":
            for s in track.get("segments", []):
                clip_m = s.get("clip") or {}
                tf_m = clip_m.get("transform") or {}
                y = tf_m.get("y", 0)
                if y < -0.45:
                    unsafe_texts += 1
    if unsafe_texts > 0:
        score -= 15
        issues.append({
            "type": "SAFE_ZONE_VIOLATION",
            "severity": "WARNING",
            "message": f"{unsafe_texts} phụ đề nằm quá sát đáy (dưới -0.45) nguy cơ bị caption TikTok che",
            "fix_action": "Kéo toàn bộ về y = -0.404"
        })
        
    # 2. Audit Subtitle Word Length (Single line rule)
    long_texts = 0
    for t in texts:
        try:
            c_obj = json.loads(t.get("content", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
        txt = c_obj.get("text", "")
        if len(txt.split()) > 10:
            long_texts += 1
    if long_texts > 0:
        score -= 10
        issues.append({
            "type": "SUBTITLE_OVERFLOW",
            "severity": "WARNING",
            "message": f"{long_texts} phụ đề dài quá 10 từ, nguy cơ tràn thành 3 dòng che sản phẩm",
            "fix_action": "Bẻ đôi câu phụ đề dài"
        })

    # 3. Audit Dead Outro
    total_dur = data.get("duration", 0)
    max_voice = 0
    for track in data.get("tracks", []):
        if track.get("type") in ["audio", "text"]:
            for s in track.get("segments", []):
                tr = s.get("target_timerange") or {}
                end = tr.get("start", 0) + tr.get("duration", 0)
                if end > max_voice:
                    max_voice = end
                
    if total_dur > max_voice + 1_500_000 and max_voice > 0:
        excess_sec = (total_dur - max_voice) / 1e6
        score -= 20
        issues.append({
            "type": "DEAD_OUTRO",
            "severity": "CRITICAL",
            "message": f"Phát hiện đuôi video chết dài {excess_sec:.1f}s sau khi dứt lời thoại (nguy cơ tụt retention)",
            "fix_action": f"Cắt cụt timeline tại {(max_voice + 400000)/1e6:.2f}s"
        })

    return {
        "project_name": project_name,
        "score": max(20, score),
        "status": "PASS" if score >= 85 else ("WARNING" if score >= 60 else "POOR"),
        "total_issues": len(issues),
        "issues": issues
    }

def scan_project_errors_core(project_name: str) -> Dict[str, Any]:
    """Quét chi tiết các lỗi trên timeline: safe zone, Montserrat shadow, letterbox, media offline, outro gap."""
    draft_file = get_draft_file(project_name)
    draft_dir = draft_file.parent
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    errors = []
    texts_map = {t.get("id"): t for t in (data.get("materials") or {}).get("texts", [])}
    videos_map = {v.get("id"): v for v in (data.get("materials") or {}).get("videos", [])}
    
    # 1. Scan tracks
    for t_idx, track in enumerate(data.get("tracks", [])):
        ttype = track.get("type")
        for seg in track.get("segments", []):
            sid = seg.get("id")
            trange = seg.get("target_timerange") or {}
            start_us = trange.get("start", 0)
            dur_us = trange.get("duration", 0)
            end_us = start_us + dur_us
            mid = seg.get("material_id")
            
            if ttype == "text":
                clip_meta = seg.get("clip") or {}
                tf = clip_meta.get("transform") or {}
                y = tf.get("y", 0.0)
                t_obj = texts_map.get(mid) or {}
                try:
                    c_obj = json.loads(t_obj.get("content", "{}"))
                    txt = c_obj.get("text", "")
                    styles = c_obj.get("styles") or []
                except Exception:
                    txt, styles = "", []
                
                # Check TikTok Lower-Third Safe Zone
                if y < -0.42:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"safe_bot_{sid}",
                        "type": "SAFE_ZONE_VIOLATION",
                        "severity": "CRITICAL",
                        "category": "safe_zone",
                        "title": f"Phụ đề chạm vùng nguy hiểm TikTok (y = {y:.2f})",
                        "description": f"Chữ \"{txt[:35]}\" nằm tại y = {y:.2f}, bị thanh caption hoặc menu TikTok/Shorts che.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 10.0,
                            "top": round(top_pct, 1),
                            "width": 80.0,
                            "height": 13.0,
                            "unit": "percent"
                        },
                        "fix_command": "Kéo toạ độ phụ đề về vùng an toàn TikTok y = -0.404",
                        "fixed": False
                    })
                elif y > 0.44:
                    top_pct = max(5.0, min(85.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"safe_top_{sid}",
                        "type": "SAFE_ZONE_TOP",
                        "severity": "WARNING",
                        "category": "safe_zone",
                        "title": f"Phụ đề nằm sát mép trên (y = {y:.2f})",
                        "description": f"Chữ \"{txt[:35]}\" nằm quá cao, nguy cơ bị notch camera, status bar hoặc tên nhạc che.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 10.0,
                            "top": round(top_pct, 1),
                            "width": 80.0,
                            "height": 13.0,
                            "unit": "percent"
                        },
                        "fix_command": "Kéo toạ độ phụ đề về vùng an toàn trên y = 0.35",
                        "fixed": False
                    })
                
                # Check Montserrat Shadow standard
                has_shadow = any(len(s.get("shadows") or []) > 0 for s in styles) if styles else False
                if not has_shadow and txt:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"style_{sid}",
                        "type": "UNSTYLED_SUBTITLE",
                        "severity": "INFO",
                        "category": "typography",
                        "title": "Phụ đề thiếu chuẩn Montserrat Commercial Shadow",
                        "description": f"Chữ \"{txt[:35]}\" chưa có shadow -45 độ, dễ bị chìm mờ khi nền video chuyển động sáng.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 12.0,
                            "top": round(top_pct, 1),
                            "width": 76.0,
                            "height": 12.0,
                            "unit": "percent"
                        },
                        "fix_command": "Áp dụng chuẩn Montserrat Shadow cho clip này",
                        "fixed": False
                    })
                
                # Check text length / word count
                words = txt.split()
                if len(words) > 10:
                    top_pct = max(10.0, min(88.0, (1.0 - y) / 2.0 * 100.0 - 6.0))
                    errors.append({
                        "id": f"overflow_{sid}",
                        "type": "SUBTITLE_OVERFLOW",
                        "severity": "WARNING",
                        "category": "typography",
                        "title": f"Phụ đề dài {len(words)} từ (Nguy cơ tràn 3 dòng)",
                        "description": f"Câu \"{txt[:35]}...\" quá dài làm mất nhịp thị giác, cần ngắt thành câu ngắn gọn.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 50_000,
                        "bbox": {
                            "left": 8.0,
                            "top": round(top_pct, 1),
                            "width": 84.0,
                            "height": 14.0,
                            "unit": "percent"
                        },
                        "fix_command": "Tối ưu ngắt câu phụ đề",
                        "fixed": False
                    })
            
            elif ttype == "video":
                clip_meta = seg.get("clip") or {}
                scale_meta = clip_meta.get("scale") or {}
                scale_x = scale_meta.get("x", 1.0)
                v_obj = videos_map.get(mid) or {}
                raw_path = v_obj.get("path", "") or v_obj.get("media_path", "")
                resolved_p = resolve_draft_path(raw_path, draft_dir)
                
                # Check missing media
                if resolved_p and not Path(resolved_p).exists():
                    errors.append({
                        "id": f"offline_{sid}",
                        "type": "MEDIA_OFFLINE",
                        "severity": "CRITICAL",
                        "category": "footage",
                        "title": f"Footage offline: {os.path.basename(resolved_p)}",
                        "description": f"Không tìm thấy tệp media tại đường dẫn: {resolved_p}",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 100_000,
                        "bbox": {
                            "left": 5.0,
                            "top": 5.0,
                            "width": 90.0,
                            "height": 90.0,
                            "unit": "percent"
                        },
                        "fix_command": "Liên kết lại tệp media trong thư mục scratch",
                        "fixed": False
                    })
                
                # Check Letterbox / Black Bars (scale < 1.0)
                if scale_x < 1.0:
                    errors.append({
                        "id": f"letterbox_{sid}",
                        "type": "LETTERBOX_BLACK_BARS",
                        "severity": "WARNING",
                        "category": "framing",
                        "title": f"Footage viền đen (Scale = {scale_x:.2f}x)",
                        "description": f"Clip {os.path.basename(resolved_p) or sid} thu nhỏ dưới 1.0x, để lộ viền đen quanh khung 9:16.",
                        "segment_id": sid,
                        "track_index": t_idx,
                        "start_us": start_us,
                        "end_us": end_us,
                        "target_time_us": start_us + 100_000,
                        "bbox": {
                            "left": 4.0,
                            "top": 4.0,
                            "width": 92.0,
                            "height": 92.0,
                            "unit": "percent"
                        },
                        "fix_command": "Áp dụng Punch-in Zoom 1.15x loại bỏ viền đen",
                        "fixed": False
                    })
    
    # 2. Check Dead Outro gap
    total_dur = data.get("duration", 0)
    max_voice = 0
    for t in data.get("tracks", []):
        if t.get("type") in ["audio", "text"]:
            for s in t.get("segments", []):
                tr = s.get("target_timerange") or {}
                e = tr.get("start", 0) + tr.get("duration", 0)
                if e > max_voice:
                    max_voice = e
                
    if total_dur > max_voice + 1_200_000 and max_voice > 0:
        excess = (total_dur - max_voice) / 1e6
        errors.append({
            "id": "dead_outro",
            "type": "DEAD_OUTRO",
            "severity": "CRITICAL",
            "category": "pacing",
            "title": f"Phát hiện đuôi video chết ({excess:.1f}s)",
            "description": f"Hình ảnh kéo dài {excess:.1f}s sau khi dứt lời thoại, gây rớt tỷ lệ hoàn thành video.",
            "segment_id": "",
            "track_index": 0,
            "start_us": max_voice,
            "end_us": total_dur,
            "target_time_us": max_voice + 200_000,
            "bbox": {
                "left": 10.0,
                "top": 15.0,
                "width": 80.0,
                "height": 70.0,
                "unit": "percent"
            },
            "fix_command": f"Triệt tiêu đuôi video chết, cắt gọn tại {(max_voice + 400_000)/1e6:.2f}s",
            "fixed": False
        })
        
    errors.sort(key=lambda x: x["start_us"])
    
    crit_count = sum(1 for e in errors if e["severity"] == "CRITICAL")
    warn_count = sum(1 for e in errors if e["severity"] == "WARNING")
    info_count = sum(1 for e in errors if e["severity"] == "INFO")
    
    calc_score = 100 - (crit_count * 15) - (warn_count * 5) - (info_count * 2)
    final_score = max(20, min(100, calc_score)) if len(errors) > 0 else 100
    
    return {
        "project_name": project_name,
        "total_errors": len(errors),
        "critical_count": crit_count,
        "warning_count": warn_count,
        "info_count": info_count,
        "health_score": final_score,
        "status": "PASS" if final_score >= 85 else ("WARNING" if final_score >= 60 else "CRITICAL"),
        "errors": errors
    }

def auto_fix_step_core(project_name: str, error_id: str) -> Dict[str, Any]:
    """Tự động sửa một lỗi cụ thể theo error_id."""
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    action_note = ""
    err_id = error_id
    
    if err_id.startswith("safe_bot_") or err_id.startswith("safe_top_"):
        seg_id = err_id.replace("safe_bot_", "").replace("safe_top_", "")
        target_y = -0.404 if err_id.startswith("safe_bot_") else 0.35
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["transform"] = s["clip"].get("transform") or {}
                    s["clip"]["transform"]["y"] = target_y
                    action_note = f"✓ Đã dịch chuyển toạ độ phụ đề về y = {target_y} (Chuẩn an toàn TikTok)"
                    break
    elif err_id.startswith("style_"):
        seg_id = err_id.replace("style_", "")
        font_path = get_montserrat_font_path()
        target_mid = None
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    target_mid = s.get("material_id")
                    break
        if target_mid:
            for t in (data.get("materials") or {}).get("texts", []):
                if t.get("id") == target_mid:
                    c_obj = json.loads(t.get("content", "{}"))
                    txt_str = c_obj.get("text", "")
                    c_obj["styles"] = [{
                        "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                        "font": {"path": font_path, "id": ""},
                        "size": 11.0,
                        "bold": True,
                        "shadows": [{
                            "angle": -45,
                            "thickness_projection_angle": -45,
                            "thickness_projection_enable": False,
                            "diffuse": 0.025,
                            "alpha": 0.72,
                            "distance": 5.0,
                            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                        }],
                        "range": [0, len(txt_str)]
                    }]
                    t["content"] = json.dumps(c_obj, ensure_ascii=False)
                    action_note = f"✓ Đã áp dụng chuẩn Montserrat Commercial Shadow cho chữ '{txt_str[:25]}'"
                    break
    elif err_id.startswith("letterbox_"):
        seg_id = err_id.replace("letterbox_", "")
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                if s.get("id") == seg_id:
                    s["clip"] = s.get("clip") or {}
                    s["clip"]["scale"] = {"x": 1.15, "y": 1.15}
                    action_note = "✓ Đã áp dụng Punch-in Zoom (1.15x) loại bỏ hoàn toàn viền đen"
                    break
    elif err_id == "dead_outro":
        max_voice_end = 0
        for track in data.get("tracks", []):
            if track.get("type") in ["audio", "text"]:
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    end_time = tr.get("start", 0) + tr.get("duration", 0)
                    if end_time > max_voice_end:
                        max_voice_end = end_time
        if max_voice_end > 0:
            target_end = max_voice_end + 400_000
            data["duration"] = target_end
            for track in data.get("tracks", []):
                for s in track.get("segments", []):
                    tr = s.get("target_timerange") or {}
                    if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                        tr["duration"] = max(100_000, target_end - tr.get("start", 0))
            action_note = f"✓ Đã cắt cụt timeline tại {target_end/1e6:.2f}s, triệt tiêu khoảng chết"
            
    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)
        
    return {
        "status": "success",
        "fixed_error_id": error_id,
        "action_performed": action_note or f"✓ Đã tối ưu lỗi {error_id}"
    }

def auto_fix_all_core(project_name: str) -> Dict[str, Any]:
    """Tự động sửa toàn bộ lỗi (Safe zone, Shadow, Letterbox, Outro gap)."""
    check_capcut_not_running()
    draft_file = get_draft_file(project_name)
    
    with open(draft_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    font_path = get_montserrat_font_path()
    actions_log = []
    
    # 1. Fix all text safe zones to y = -0.404 and inject Montserrat Shadow
    fixed_texts = 0
    for track in data.get("tracks", []):
        if track.get("type") == "text":
            for s in track.get("segments", []):
                s["clip"] = s.get("clip") or {}
                s["clip"]["transform"] = s["clip"].get("transform") or {}
                s["clip"]["transform"]["y"] = -0.404
                fixed_texts += 1
                
    if fixed_texts > 0:
        actions_log.append(f"✓ Đã căn chỉnh {fixed_texts} phụ đề về Safe Zone TikTok (y = -0.404)")
        
    for t in (data.get("materials") or {}).get("texts", []):
        try:
            c_obj = json.loads(t.get("content", "{}"))
            txt_str = c_obj.get("text", "")
            c_obj["styles"] = [{
                "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                "font": {"path": font_path, "id": ""},
                "size": 11.0,
                "bold": True,
                "shadows": [{
                    "angle": -45,
                    "thickness_projection_angle": -45,
                    "thickness_projection_enable": False,
                    "diffuse": 0.025,
                    "alpha": 0.72,
                    "distance": 5.0,
                    "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}}
                }],
                "range": [0, len(txt_str)]
            }]
            t["content"] = json.dumps(c_obj, ensure_ascii=False)
        except Exception:
            pass
    actions_log.append("✓ Đã áp dụng chuẩn Montserrat Commercial Shadow cho toàn bộ văn bản")

    # 2. Fix letterboxes (scale < 1.0)
    fixed_scales = 0
    for track in data.get("tracks", []):
        if track.get("type") == "video":
            for s in track.get("segments", []):
                s["clip"] = s.get("clip") or {}
                cur_scale = (s["clip"].get("scale") or {}).get("x", 1.0)
                if cur_scale < 1.0:
                    s["clip"]["scale"] = {"x": 1.15, "y": 1.15}
                    fixed_scales += 1
    if fixed_scales > 0:
        actions_log.append(f"✓ Đã áp dụng Punch-in Zoom (1.15x) cho {fixed_scales} clip viền đen")

    # 3. Cut Dead Outro
    max_voice_end = 0
    for track in data.get("tracks", []):
        if track.get("type") in ["audio", "text"]:
            for s in track.get("segments", []):
                tr = s.get("target_timerange") or {}
                end_time = tr.get("start", 0) + tr.get("duration", 0)
                if end_time > max_voice_end:
                    max_voice_end = end_time
    if max_voice_end > 0:
        target_end = max_voice_end + 400_000
        data["duration"] = target_end
        for track in data.get("tracks", []):
            for s in track.get("segments", []):
                tr = s.get("target_timerange") or {}
                if tr.get("start", 0) + tr.get("duration", 0) > target_end:
                    tr["duration"] = max(100_000, target_end - tr.get("start", 0))
        actions_log.append(f"✓ Đã triệt tiêu đuôi chết, chốt timeline dứt khoát tại {target_end/1e6:.2f}s")

    recalculate_project_duration(data)
    save_draft_with_history(draft_file, data)

    return {
        "status": "success",
        "actions_performed": actions_log,
        "message": f"Đã tối ưu tự động hoàn tất {len(actions_log)} hạng mục"
    }
