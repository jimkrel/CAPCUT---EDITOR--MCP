css_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\static\style.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

stepper_and_inspector_css = """
/* ==========================================
   CLIP INSPECTOR CONTROLS & PINNED ACTIONS
   ========================================== */

#viewClipInspector {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

#viewClipInspector .details-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 12px;
}

.insp-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  align-items: center;
}

.num-stepper {
  display: inline-flex;
  align-items: center;
  background: #14161a;
  border: 1px solid #2d313d;
  border-radius: 5px;
  overflow: hidden;
  height: 28px;
  width: 100%;
}

.num-stepper button {
  background: #20242d;
  border: none;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 700;
  width: 30px;
  height: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.num-stepper button:hover {
  background: #2b3140;
  color: #fff;
}

.num-stepper input {
  flex: 1;
  background: transparent;
  border: none;
  color: #f1f5f9;
  font-size: 11.5px;
  font-family: monospace;
  font-weight: 600;
  text-align: center;
  width: 100%;
  min-width: 0;
  outline: none;
}

.scale-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.scale-btn {
  background: #181b22;
  border: 1px solid #2a2f3c;
  color: #94a3b8;
  font-size: 10.5px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.scale-btn:hover {
  background: #252b38;
  color: #fff;
  border-color: #3b4356;
}

.scale-btn.active {
  background: rgba(0, 229, 255, 0.12);
  border-color: #00e5ff;
  color: #00e5ff;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.25);
}

.insp-actions {
  position: sticky;
  bottom: 0;
  background: #15171d;
  border-top: 1px solid #262a34;
  padding: 8px 10px;
  margin-top: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  z-index: 20;
  box-shadow: 0 -4px 15px rgba(0, 0, 0, 0.6);
}

.btn-insp-action {
  background: #212530;
  border: 1px solid #333a4a;
  color: #e2e8f0;
  font-size: 10.5px;
  font-weight: 600;
  padding: 6px 6px;
  border-radius: 5px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
  transition: all 0.15s;
}

.btn-insp-action:hover {
  background: #2a3040;
  border-color: #00e5ff;
  color: #fff;
  transform: translateY(-1px);
}

.btn-insp-action.btn-ai {
  background: linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(124, 58, 237, 0.2));
  border-color: rgba(0, 229, 255, 0.4);
  color: #00e5ff;
}

.btn-insp-action.btn-ai:hover {
  background: linear-gradient(135deg, rgba(0, 229, 255, 0.25), rgba(124, 58, 237, 0.35));
  border-color: #00e5ff;
}

.btn-insp-action.btn-danger {
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.08);
}

.btn-insp-action.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
}
"""

css += "\n" + stepper_and_inspector_css

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

print("Inspector & Stepper controls styled successfully!")
