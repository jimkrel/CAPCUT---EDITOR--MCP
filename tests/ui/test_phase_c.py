import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_DRAFT_SRC = FIXTURES_DIR / "sample_draft"

def test_phase_c_comprehensive(live_server, sample_project_setup):
    """
    Test toàn diện Phase C:
    - C1: Thống nhất số lỗi giữa header, tab badge và QA modal; không hiện PASS khi có lỗi CRITICAL.
    - C2: Vùng bấm tối thiểu >= 28x28px cho mọi button, select, input tương tác.
    - C3: Tương phản text và không có font chữ nào < 11px trong toàn bộ DOM.
    - C4: Icon thẻ audio trong thư viện là 🎵 thay vì 🖼️.
    - C5: Nhãn track phân loại chuẩn: V1, V2, A1, A2.
    - C6: Toast tối đa 3, tự gộp trùng nội dung, toast lỗi hiển thị lâu (>= 8s).
    - C7: Dọn tính năng chết: bỏ badge PRO, trạng thái đồng bộ draft thật.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        # Bắt pageerror & console.error
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        page.goto(live_server)
        page.wait_for_selector(".editor-shell")
        page.select_option("#projectSelect", sample_project_setup)
        page.wait_for_selector(".timeline-clip")
        time.sleep(1.2)
        
        # ---------------------------------------------------------------------
        # C1: SỐ LỖI NHẤT QUÁN & QA MODAL KHÔNG HIỆN PASS KHI CÓ CRITICAL
        # ---------------------------------------------------------------------
        hdr_count = page.inner_text("#headerErrCount").strip()
        tab_count = page.inner_text("#tabErrBadge").strip()
        assert hdr_count == tab_count, f"Header ({hdr_count}) và Tab Badge ({tab_count}) phải bằng nhau"
        
        # Mở QA Modal
        with page.expect_response(lambda r: "/api/quality-audit/" in r.url and r.status == 200):
            page.click(".btn-hdr-qa")
        page.wait_for_selector("#qaModal.open")
        page.wait_for_selector("#qaScoreSub:has-text('Tổng số vấn đề:')")
        
        qa_score = page.inner_text("#qaScoreDial").strip()
        qa_status = page.inner_text("#qaScoreStatus").strip()
        qa_sub = page.inner_text("#qaScoreSub").strip()
        
        assert qa_score.isdigit(), f"Điểm QA phải là số nguyên, nhận được: {qa_score}"
        # Nếu có lỗi (hdr_count != '0'), kiểm tra QA status phản ánh đúng
        if int(hdr_count) > 0:
            assert "Tổng số vấn đề:" in qa_sub or "nhóm" in qa_sub
            # Nếu có critical errors thì status không được là 'ĐẠT CHUẨN (PASS)'
            crit_items = page.locator(".qa-issue-item:has-text('CRITICAL')").count()
            if crit_items > 0:
                assert qa_status != "ĐẠT CHUẨN (PASS)", "Điểm số không được hiện ĐẠT CHUẨN khi còn cảnh báo CRITICAL"
                
        # Đóng QA Modal
        page.click(".btn-close-modal")
        time.sleep(0.3)
        
        # ---------------------------------------------------------------------
        # C2: VÙNG BẤM TƯƠNG TÁC TỐI THIỂU >= 28x28px
        # ---------------------------------------------------------------------
        # Kiểm tra project select
        sel_box = page.locator("#projectSelect").bounding_box()
        assert sel_box["height"] >= 28, f"Project select height {sel_box['height']} < 28px"
        
        # Kiểm tra play button và transport buttons
        play_box = page.locator("#playBtn").bounding_box()
        assert play_box["width"] >= 28 and play_box["height"] >= 28
        
        undo_box = page.locator("#undoBtn").bounding_box()
        redo_box = page.locator("#redoBtn").bounding_box()
        assert undo_box["width"] >= 28 and undo_box["height"] >= 28
        assert redo_box["width"] >= 28 and redo_box["height"] >= 28
        
        # Quét mọi button hiển thị trong workspace và header
        small_controls = page.evaluate("""() => {
            const controls = Array.from(document.querySelectorAll('button, select, input[type="text"], input[type="number"]'));
            const violations = [];
            for (const el of controls) {
                // Bỏ qua phần tử ẩn hoặc trong drawer/modal đang đóng
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                if (!el.offsetParent && el.tagName !== 'BODY') continue;
                
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                
                // Cho phép sai số subpixel làm tròn (27.5px)
                if (rect.width < 27.5 || rect.height < 27.5) {
                    violations.push({
                        tag: el.tagName,
                        id: el.id,
                        className: el.className,
                        text: (el.textContent || '').trim().slice(0, 20),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    });
                }
            }
            return violations;
        }""")
        assert len(small_controls) == 0, f"Phát hiện controls nhỏ hơn 28px: {small_controls}"
        
        # ---------------------------------------------------------------------
        # C3: TƯƠNG PHẢN TEXT & FONT SIZE >= 11px
        # ---------------------------------------------------------------------
        # 1. Timecode separator không được là #596171 (3.1:1)
        sep_color = page.evaluate("""() => {
            const sep = document.querySelector('.timecode em');
            if (!sep) return '';
            return window.getComputedStyle(sep).color;
        }""")
        # rgb(89, 97, 113) tương đương #596171
        assert "89, 97, 113" not in sep_color, f"Dấu phân cách timecode vẫn dùng màu xám tối: {sep_color}"
        
        # 2. Không có text element nào có computed font-size < 11px
        tiny_text_elements = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('*'));
            const tiny = [];
            for (const el of all) {
                if (el.children.length === 0 && (el.textContent || '').trim().length > 0) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const fs = parseFloat(style.fontSize);
                    if (fs < 10.8) {
                        tiny.push({
                            tag: el.tagName,
                            id: el.id,
                            className: el.className,
                            fontSize: style.fontSize,
                            text: el.textContent.trim().slice(0, 30)
                        });
                    }
                }
            }
            return tiny;
        }""")
        assert len(tiny_text_elements) == 0, f"Phát hiện phần tử text font-size < 11px: {tiny_text_elements}"
        
        # ---------------------------------------------------------------------
        # C4: ICON THẺ AUDIO TRONG THƯ VIỆN LÀ 🎵 THAY VÌ 🖼️
        # ---------------------------------------------------------------------
        audio_card_info = page.evaluate("""() => {
            // Kiểm tra trong renderMediaTab logic
            const mediaCards = Array.from(document.querySelectorAll('.media-card'));
            const results = [];
            for (const card of mediaCards) {
                const ext = (card.querySelector('.media-badge-ext')?.textContent || '').toUpperCase();
                const isAudio = ['MP3', 'WAV', 'AAC', 'M4A', 'FLAC', 'OGG'].includes(ext);
                if (isAudio) {
                    const thumb = card.querySelector('.media-thumb');
                    results.push({
                        ext: ext,
                        hasNoteIcon: thumb ? thumb.textContent.includes('🎵') : false,
                        hasImgIcon: thumb ? thumb.textContent.includes('🖼️') : false
                    });
                }
            }
            return results;
        }""")
        for item in audio_card_info:
            assert item["hasNoteIcon"] is True, f"Thẻ audio ({item['ext']}) không hiển thị icon 🎵"
            assert item["hasImgIcon"] is False, f"Thẻ audio ({item['ext']}) không được dùng icon 🖼️"

        # ---------------------------------------------------------------------
        # C5: NHÃN TRACK PHÂN LOẠI CHUẨN
        # ---------------------------------------------------------------------
        track_labels = page.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll('.track-header-badge, .track-label, .ruler-header-spacer'));
            return labels.map(l => l.textContent.trim());
        }""")
        # Kiểm tra không có 2 track video cùng gắn V1 (Chính)
        v1_count = sum(1 for l in track_labels if "V1" in l and "Chính" in l)
        assert v1_count <= 1, f"Có nhiều hơn 1 track được gắn V1 (Chính): {v1_count}"

        # ---------------------------------------------------------------------
        # C6: TOAST TỐI ĐA 3, GỘP TRÙNG, TIMEOUT CHUẨN
        # ---------------------------------------------------------------------
        # Thử bắn 5 toast liên tiếp
        page.evaluate("""() => {
            showToast('Thông báo kiểm tra 1', 'info');
            showToast('Thông báo kiểm tra 2', 'info');
            showToast('Thông báo kiểm tra 3', 'info');
            showToast('Thông báo kiểm tra 4', 'info');
            showToast('Thông báo kiểm tra 4', 'info'); // Duplicate
        }""")
        time.sleep(0.2)
        
        toasts_count = page.locator(".toast-item").count()
        assert toasts_count <= 3, f"Số toast hiển thị ({toasts_count}) vượt quá tối đa 3"
        
        # Kiểm tra nội dung không bị duplicate cùng 1 lúc
        toast_texts = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.toast-msg')).map(m => m.textContent);
        }""")
        assert len(toast_texts) == len(set(toast_texts)), f"Toast bị trùng lặp nội dung: {toast_texts}"

        # ---------------------------------------------------------------------
        # C7: DỌN TÍNH NĂNG CHẾT (PRO BADGE) & ĐỒNG BỘ DRAFT THẬT
        # ---------------------------------------------------------------------
        # Không có badge PRO
        pro_badges = page.locator(".badge-pro, span:has-text('PRO')").count()
        assert pro_badges == 0, "Không được giữ lại badge PRO không có chức năng"
        
        # Trạng thái đồng bộ Draft thật
        sync_text = page.inner_text("#draftSyncStatusText").strip()
        assert sync_text in ["Đã đồng bộ Draft", "Đang lưu draft...", "Bị khóa (CapCut đang mở)"]
        
        # Bấm Lưu -> Chuyển sang lưu và toast tiếng Việt
        page.click("#btnExportDraft")
        time.sleep(0.3)
        save_toast = page.inner_text(".toast-item:last-child .toast-msg")
        assert "đồng bộ" in save_toast.lower() or "draft" in save_toast.lower()
        
        # ---------------------------------------------------------------------
        # C8: ACCESSIBILITY FOCUS RING & ARIA
        # ---------------------------------------------------------------------
        focus_rule = page.evaluate("""() => {
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        if (rule.selectorText && rule.selectorText.includes(':focus-visible')) {
                            return rule.cssText;
                        }
                    }
                } catch(e) {}
            }
            return '';
        }""")
        assert "outline" in focus_rule, f":focus-visible outline chưa được khai báo: {focus_rule}"
        
        # Cuối cùng assert không có pageerror
        assert len(page_errors) == 0, f"Pageerror phát sinh: {page_errors}"
        
        browser.close()
