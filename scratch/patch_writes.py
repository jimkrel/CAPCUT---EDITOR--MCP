server_path = r"C:\Users\jinnr\.gemini\antigravity-ide\scratch\capcut-web-studio\server.py"
with open(server_path, "r", encoding="utf-8") as f:
    text = f.read()

old_write = """    with open(draft_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)"""

new_write = """    save_draft_safely_py(draft_file, data)"""

text = text.replace(old_write, new_write)

with open(server_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Remaining raw writes replaced with save_draft_safely_py!")
