import re

# 1. Update index.html: pin insp-actions outside details-content
html_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\static\index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

old_insp_block = """          <!-- Inspector Action Buttons -->
          <div class="insp-actions">
            <button type="button" class="btn-insp-action" onclick="splitSelectedAtPlayhead()">✂ Cắt đôi tại Playhead</button>
            <button type="button" class="btn-insp-action" onclick="duplicateSelected()">📋 Nhân đôi</button>
            <button type="button" class="btn-insp-action btn-ai" onclick="openClipAIPanel()">🪄 Ra lệnh AI</button>
            <button type="button" class="btn-insp-action btn-danger" onclick="deleteSelected()">🗑 Xóa Clip</button>
          </div>
        </div>
      </div>"""

new_insp_block = """        </div>
      </div>
      <!-- Pinned Action Buttons: Always visible regardless of scrolling -->
      <div class="insp-actions">
        <button type="button" class="btn-insp-action" onclick="splitSelectedAtPlayhead()">✂ Cắt đôi</button>
        <button type="button" class="btn-insp-action" onclick="duplicateSelected()">📋 Nhân đôi</button>
        <button type="button" class="btn-insp-action btn-ai" onclick="openClipAIPanel()">🪄 AI Lệnh</button>
        <button type="button" class="btn-insp-action btn-danger" onclick="deleteSelected()">🗑 Xóa Clip</button>
      </div>
    </div>"""

html = html.replace(old_insp_block, new_insp_block)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

# 2. Update style.css: layout widths & tab styles
css_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\static\style.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

css = css.replace(
    "grid-template-columns: 310px 270px 1fr; min-height: 0;",
    "grid-template-columns: 330px 285px 1fr; min-height: 0;"
)

css = css.replace(
    "padding: 8px 8px;\n  white-space: nowrap;\n  color: var(--text-muted);\n  cursor: pointer;\n  display: flex;\n  align-items: center;\n  gap: 4px;\n  font-size: 10.5px;",
    "padding: 7px 6px;\n  white-space: nowrap;\n  color: var(--text-muted);\n  cursor: pointer;\n  display: flex;\n  align-items: center;\n  gap: 3px;\n  font-size: 10px;"
)

# Ensure #viewClipInspector has display: flex when active and handles pinned footer
css += """
#viewClipInspector.active {
  display: flex !important;
  flex-direction: column !important;
  height: 100% !important;
  overflow: hidden !important;
}

#viewClipInspector .details-content {
  flex: 1 !important;
  overflow-y: auto !important;
}
"""

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("Pinned inspector actions & tab widths successfully updated!")
