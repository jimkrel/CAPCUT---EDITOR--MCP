import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

VIEWPORTS = [
    (1920, 1080),
    (1440, 900),
    (1366, 768),
    (1024, 768),
    (800, 600)
]

def test_phase_b_layout_across_5_viewports(live_server, sample_project_setup):
    screenshot_dir = Path("tests/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        
        for w, h in VIEWPORTS:
            context = browser.new_context(viewport={"width": w, "height": h})
            page = context.new_page()
            
            page_errors = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            
            page.goto("http://127.0.0.1:8765/")
            page.wait_for_selector("#projectSelect")
            page.select_option("#projectSelect", sample_project_setup)
            time.sleep(0.6)
            
            # 1. document.documentElement.scrollWidth <= innerWidth & không scroll dọc toàn trang
            scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
            inner_width = page.evaluate("() => window.innerWidth")
            scroll_height = page.evaluate("() => document.documentElement.scrollHeight")
            inner_height = page.evaluate("() => window.innerHeight")
            
            assert scroll_width <= inner_width + 1, f"Horizontal scroll detected at {w}x{h}: scrollWidth={scroll_width}, innerWidth={inner_width}"
            assert scroll_height <= inner_height + 1, f"Vertical scroll detected at {w}x{h}: scrollHeight={scroll_height}, innerHeight={inner_height}"
            
            # 2. Vị trí panels so với Timeline: rect.bottom <= timeline.top + 1
            timeline_top = page.evaluate("() => document.getElementById('lowerTimeline').getBoundingClientRect().top")
            
            # Panel Player (Stage/Preview monitor) luôn luôn phải nằm trên timeline
            player_rect = page.evaluate("() => { const r = document.getElementById('panelPlayer').getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; }")
            assert player_rect["bottom"] <= timeline_top + 1, f"panelPlayer bottom ({player_rect['bottom']}) overflows below timeline top ({timeline_top}) at {w}x{h}"
            
            # Nếu panelAssets không phải drawer ẩn (hoặc khi hiển thị inline): rect.bottom <= timeline.top + 1
            if w > 1024:
                assets_rect = page.evaluate("() => { const r = document.getElementById('panelAssets').getBoundingClientRect(); return { bottom: r.bottom }; }")
                assert assets_rect["bottom"] <= timeline_top + 1, f"panelAssets bottom ({assets_rect['bottom']}) overflows below timeline top ({timeline_top}) at {w}x{h}"
            
            # Nếu panelDetails không phải drawer ẩn (hoặc khi hiển thị inline): rect.bottom <= timeline.top + 1
            if w > 1280:
                details_rect = page.evaluate("() => { const r = document.getElementById('panelDetails').getBoundingClientRect(); return { bottom: r.bottom }; }")
                assert details_rect["bottom"] <= timeline_top + 1, f"panelDetails bottom ({details_rect['bottom']}) overflows below timeline top ({timeline_top}) at {w}x{h}"

            # 3. elementFromPoint tại tâm #playBtn trả đúng #playBtn (hoặc con của nó); bấm thật vào nút Play thì isPlaying đổi
            play_btn_point_check = page.evaluate("""() => {
                const btn = document.getElementById('playBtn');
                const rect = btn.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const el = document.elementFromPoint(cx, cy);
                return {
                    matched: (el === btn || btn.contains(el)),
                    foundTag: el ? el.tagName : null,
                    foundClass: el ? el.className : null,
                    btnRect: { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right }
                };
            }""")
            assert play_btn_point_check["matched"], f"elementFromPoint at #playBtn returned {play_btn_point_check['foundTag']}.{play_btn_point_check['foundClass']} instead of #playBtn at {w}x{h}"
            
            # Bấm thật vào PlayBtn và kiểm tra isPlaying thay đổi
            initial_playing = page.evaluate("() => isPlaying")
            page.locator("#playBtn").click()
            time.sleep(0.2)
            after_playing = page.evaluate("() => isPlaying")
            assert after_playing != initial_playing, f"Clicking #playBtn did not toggle isPlaying at {w}x{h}"
            # Trả về trạng thái dừng
            if after_playing:
                page.locator("#playBtn").click()
                time.sleep(0.1)

            # 4. Mọi nút trong header có rect.right <= innerWidth và rect.bottom <= header.bottom; nút Lưu/Lỗi luôn nhìn thấy
            header_check = page.evaluate("""() => {
                const header = document.querySelector('header.topbar');
                const hRect = header.getBoundingClientRect();
                const buttons = Array.from(header.querySelectorAll('button:not([style*="display: none"]), select, .export-button'));
                const results = [];
                for (const b of buttons) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        results.push({
                            id: b.id || b.className,
                            right: r.right,
                            bottom: r.bottom,
                            headerBottom: hRect.bottom,
                            windowWidth: window.innerWidth,
                            overflowX: r.right > window.innerWidth,
                            overflowY: r.bottom > hRect.bottom + 1
                        });
                    }
                }
                const btnSave = document.getElementById('btnExportDraft');
                const btnQa = document.querySelector('.btn-hdr-qa');
                return {
                    results: results,
                    btnSaveVisible: Boolean(btnSave && btnSave.getBoundingClientRect().width > 0),
                    btnQaVisible: Boolean(btnQa && btnQa.getBoundingClientRect().width > 0)
                };
            }""")
            
            for item in header_check["results"]:
                assert not item["overflowX"], f"Header element {item['id']} overflows X at {w}x{h}: right={item['right']} > {item['windowWidth']}"
                assert not item["overflowY"], f"Header element {item['id']} overflows Y below header at {w}x{h}: bottom={item['bottom']} > {item['headerBottom']}"
            
            assert header_check["btnSaveVisible"], f"Save button '#btnExportDraft' must be visible at {w}x{h}"
            assert header_check["btnQaVisible"], f"QA Error button '.btn-hdr-qa' must be visible at {w}x{h}"
            
            # 5. Chụp screenshot lưu vào tests/screenshots/
            screenshot_path = screenshot_dir / f"viewport_{w}x{h}.png"
            page.screenshot(path=str(screenshot_path))
            assert screenshot_path.exists(), f"Screenshot not saved for {w}x{h}"
            
            # 6. Không có page error
            assert len(page_errors) == 0, f"Page errors encountered at {w}x{h}: {page_errors}"
            
            context.close()
            
        browser.close()
