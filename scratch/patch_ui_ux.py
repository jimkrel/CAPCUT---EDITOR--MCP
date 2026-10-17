import re

# 1. Update index.html
html_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\static\index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Header right buttons optimization
old_header_right = """    <div class="header-right">
      <button class="btn-mcp-timeline" onclick="openMcpModal()">
        <span class="mcp-symbol">⚡</span> MCP Tạo Timeline
      </button>
      <button class="btn-live-agent" onclick="toggleLiveAgentModal()">
        <span class="agent-pulse"></span> 🤖 AI AGENT EDIT (REALTIME)
      </button>
      <button class="btn-qa-audit" onclick="openQAModal()">
        <span class="pulse-dot"></span> 🔍 Quét Lỗi (<span id="headerErrCount">0</span>)
      </button>
      <div class="btn-pro"><span class="crown">👑</span> Pro</div>
      <div class="btn-share">Chia sẻ</div>
      <div class="btn-export">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Xuất
      </div>
      <div class="win-controls">
        <span>─</span><span>□</span><span>✕</span>
      </div>
    </div>"""

new_header_right = """    <div class="header-right">
      <button class="btn-mcp-timeline" onclick="openMcpModal()" title="MCP Tạo Timeline 13 Lớp">
        <span class="mcp-symbol">⚡</span> MCP Timeline
      </button>
      <button class="btn-live-agent" onclick="toggleLiveAgentModal()" title="Mở Cockpit AI Agent Edit Thời Gian Thực">
        <span class="agent-pulse"></span> 🤖 AI Agent
      </button>
      <button class="btn-qa-audit" onclick="openQAModal()" title="Kiểm định chất lượng dự án">
        <span class="pulse-dot"></span> 🔍 Lỗi (<span id="headerErrCount">0</span>)
      </button>
      <div class="btn-pro hide-on-compact"><span class="crown">👑</span> Pro</div>
      <div class="btn-share hide-on-compact">Chia sẻ</div>
      <div class="btn-export">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Xuất
      </div>
      <div class="win-controls hide-on-compact">
        <span>─</span><span>□</span><span>✕</span>
      </div>
    </div>"""

html = html.replace(old_header_right, new_header_right)

# Asset tabs compacting
old_tabs = """      <div class="asset-tab-bar">
        <div class="asset-tab active" onclick="switchAssetTab('scanner', this)" id="tabScannerBtn"><span class="tab-icon">🎯</span> Quét Lỗi <span class="tab-err-badge" id="tabErrBadge">0</span></div>
        <div class="asset-tab" onclick="switchAssetTab('media', this)"><span class="tab-icon">📁</span> Footage</div>
        <div class="asset-tab" onclick="switchAssetTab('text', this)"><span class="tab-icon">🔤</span> Văn bản</div>
        <div class="asset-tab" onclick="switchAssetTab('effects', this)"><span class="tab-icon">🪄</span> Hiệu ứng</div>
        <div class="asset-tab" onclick="switchAssetTab('transitions', this)"><span class="tab-icon">⚡</span> Chuyển tiếp</div>
        <div class="asset-tab" onclick="switchAssetTab('adjust', this)"><span class="tab-icon">🎚️</span> Điều chỉnh</div>
      </div>"""

new_tabs = """      <div class="asset-tab-bar">
        <div class="asset-tab active" onclick="switchAssetTab('scanner', this)" id="tabScannerBtn" title="Quét lỗi footage & timeline"><span class="tab-icon">🎯</span> Lỗi <span class="tab-err-badge" id="tabErrBadge">0</span></div>
        <div class="asset-tab" onclick="switchAssetTab('media', this)" title="Footage video"><span class="tab-icon">📁</span> Footage</div>
        <div class="asset-tab" onclick="switchAssetTab('text', this)" title="Văn bản & Phụ đề"><span class="tab-icon">🔤</span> Chữ</div>
        <div class="asset-tab" onclick="switchAssetTab('effects', this)" title="Hiệu ứng video"><span class="tab-icon">🪄</span> FX</div>
        <div class="asset-tab" onclick="switchAssetTab('transitions', this)" title="Chuyển tiếp"><span class="tab-icon">⚡</span> Chuyển</div>
        <div class="asset-tab" onclick="switchAssetTab('adjust', this)" title="Điều chỉnh màu sắc"><span class="tab-icon">🎚️</span> Chỉnh</div>
      </div>"""

html = html.replace(old_tabs, new_tabs)

# Compact error chips
old_chips = """          <div class="error-filter-chips">
            <span class="err-chip active" data-filter="all" onclick="filterErrorList('all', this)">Tất cả (<b id="filterAllCount">0</b>)</span>
            <span class="err-chip type-safe" data-filter="safe_zone" onclick="filterErrorList('safe_zone', this)">🛡️ Safe Zone (<b id="filterSafeCount">0</b>)</span>
            <span class="err-chip type-letterbox" data-filter="framing" onclick="filterErrorList('framing', this)">🔲 Viền Đen (<b id="filterFramingCount">0</b>)</span>
            <span class="err-chip type-dead" data-filter="pacing" onclick="filterErrorList('pacing', this)">✂️ Đuôi Chết (<b id="filterPacingCount">0</b>)</span>
            <span class="err-chip type-style" data-filter="typography" onclick="filterErrorList('typography', this)">✨ Font & Shadow (<b id="filterTypoCount">0</b>)</span>
          </div>"""

new_chips = """          <div class="error-filter-chips">
            <span class="err-chip active" data-filter="all" onclick="filterErrorList('all', this)">Tất cả (<b id="filterAllCount">0</b>)</span>
            <span class="err-chip type-safe" data-filter="safe_zone" onclick="filterErrorList('safe_zone', this)">🛡️ Safe (<b id="filterSafeCount">0</b>)</span>
            <span class="err-chip type-letterbox" data-filter="framing" onclick="filterErrorList('framing', this)">🔲 Viền (<b id="filterFramingCount">0</b>)</span>
            <span class="err-chip type-dead" data-filter="pacing" onclick="filterErrorList('pacing', this)">✂️ Đuôi (<b id="filterPacingCount">0</b>)</span>
            <span class="err-chip type-style" data-filter="typography" onclick="filterErrorList('typography', this)">✨ Font (<b id="filterTypoCount">0</b>)</span>
          </div>"""

html = html.replace(old_chips, new_chips)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("index.html updated successfully!")
