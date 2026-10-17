css_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\static\style.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

# 1. Update .upper-workspace grid
css = css.replace(
    "grid-template-columns: 460px 1fr 400px;",
    "grid-template-columns: 310px 270px 1fr; min-height: 0;"
)

# 2. Update .lower-timeline height
css = css.replace(
    "height: 340px;\n  background: #111215;",
    "height: 245px;\n  flex-shrink: 0;\n  background: #111215;"
)

# 3. Add styling for .btn-live-agent, .hide-on-compact, and compact header buttons
header_extra_css = """
/* Responsive & Compact Header */
.hide-on-compact {
  display: flex;
}
@media (max-width: 1100px) {
  .hide-on-compact {
    display: none !important;
  }
}

.btn-live-agent {
  background: linear-gradient(135deg, #0284c7, #0369a1);
  color: #fff;
  border: 1px solid #38bdf8;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
  transition: all 0.15s;
}
.btn-live-agent:hover {
  background: #0ea5e9;
  transform: translateY(-1px);
}
.agent-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #38bdf8;
  box-shadow: 0 0 8px #38bdf8;
}

.btn-mcp-timeline {
  background: linear-gradient(135deg, #7c3aed, #4f46e5);
  color: #fff;
  border: 1px solid #a78bfa;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  box-shadow: 0 0 10px rgba(124, 58, 237, 0.3);
  transition: all 0.15s;
}
.btn-mcp-timeline:hover {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  transform: translateY(-1px);
}
"""

css = css.replace(
    ".app-header {",
    header_extra_css + "\n.app-header {"
)

# 4. Make .insp-actions sticky at the bottom of .dtab-view / .clip-inspector-box
old_insp_actions = """.insp-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
}"""

new_insp_actions = """.insp-actions {
  position: sticky;
  bottom: 0;
  background: #1a1b1f;
  border-top: 1px solid #282a30;
  padding: 8px 10px;
  margin-top: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  z-index: 10;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.5);
}"""

if old_insp_actions in css:
    css = css.replace(old_insp_actions, new_insp_actions)
else:
    # If not found directly, append sticky override
    css += """
.insp-actions {
  position: sticky !important;
  bottom: 0 !important;
  background: #1a1b1f !important;
  border-top: 1px solid #282a30 !important;
  padding: 8px 10px !important;
  margin-top: auto !important;
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  gap: 6px !important;
  z-index: 10 !important;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.5) !important;
}
"""

# 5. Fix asset tabs padding to prevent overflow
old_tab_style = """.asset-tab {
  padding: 9px 12px;
  white-space: nowrap;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  border-bottom: 2px solid transparent;
}"""

new_tab_style = """.asset-tab {
  padding: 8px 8px;
  white-space: nowrap;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  border-bottom: 2px solid transparent;
}"""

css = css.replace(old_tab_style, new_tab_style)

# 6. Fix .player-canvas to auto-scale in expanded player area
css = css.replace(
    "width: 240px;\n  height: 426px;",
    "height: calc(100% - 10px);\n  max-height: 420px;\n  aspect-ratio: 9 / 16;\n  width: auto;"
)

# 7. Fix timeline track height and scroll
css = css.replace(
    ".timeline-scroll-container {\n  flex: 1;",
    ".timeline-scroll-container {\n  flex: 1;\n  min-height: 0;\n  overflow-y: auto;"
)

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("style.css patched successfully!")
