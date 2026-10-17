import os

p = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-roughcut-studio\capcut_mcp_server.js"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

target = """  if (name === "capcut_safe_launch") {
    runCmd(`start "" "${CAPCUT_EXE}"`);
    return { ok: true, message: "Đã kích hoạt CapCut Desktop an toàn." };
  }"""

replacement = """  if (name === "capcut_safe_launch") {
    const exe = findCapcutExe();
    if (!fs.existsSync(exe)) return { ok: false, error: "Không tìm thấy CapCut.exe: " + exe };
    runCmd(`start "" "${exe}"`);
    return { ok: true, message: `Đã kích hoạt CapCut Desktop an toàn (${path.basename(path.dirname(exe))}).` };
  }"""

c_norm = c.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")

if target_norm in c_norm:
    c_norm = c_norm.replace(target_norm, replacement_norm)
    with open(p, "w", encoding="utf-8") as f:
        f.write(c_norm.replace("\n", "\r\n"))
    print("SUCCESS: capcut_safe_launch updated!")
else:
    print("TARGET NOT FOUND")
