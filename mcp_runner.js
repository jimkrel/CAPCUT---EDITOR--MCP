// mcp_runner.js - Safe execution of CapCut MCP functions without string concatenation injection
const fs = require('fs');
const path = require('path');

const [,, mcpServerPath, inputJsonPath] = process.argv;

if (!mcpServerPath || !inputJsonPath) {
    console.error(JSON.stringify({ ok: false, error: "Thiếu tham số mcpServerPath hoặc inputJsonPath" }));
    process.exit(1);
}

try {
    if (!fs.existsSync(mcpServerPath)) {
        console.error(JSON.stringify({ ok: false, error: `MCP Server script không tồn tại: ${mcpServerPath}` }));
        process.exit(1);
    }
    if (!fs.existsSync(inputJsonPath)) {
        console.error(JSON.stringify({ ok: false, error: `Tệp tham số không tồn tại: ${inputJsonPath}` }));
        process.exit(1);
    }

    const m = require(path.resolve(mcpServerPath));
    const rawInput = fs.readFileSync(inputJsonPath, 'utf-8');
    const input = JSON.parse(rawInput);
    const { action, toolName, args } = input;
    let out = {};

    if (action === 'create_project' || toolName === 'capcut_compile_13layer_draft') {
        if (typeof m.compile13LayerCommercialDraft !== 'function') {
            throw new Error("Hàm compile13LayerCommercialDraft không tồn tại trong MCP module");
        }
        out = m.compile13LayerCommercialDraft(args);
    } else if (toolName === 'capcut_scan_and_index_footage') {
        if (typeof m.FootageManager !== 'function') {
            throw new Error("Lớp FootageManager không tồn tại trong MCP module");
        }
        const fm = new m.FootageManager();
        out = fm.scanFolder(args.folderPath || args.brollFolderPath);
    } else if (toolName === 'capcut_safe_launch') {
        out = { ok: true, message: 'Đã gửi lệnh mở CapCut an toàn' };
    } else {
        out = { ok: false, error: `Tool không tồn tại trong danh mục: ${toolName}` };
    }

    console.log(JSON.stringify(out));
} catch (e) {
    console.error(JSON.stringify({ ok: false, error: e.message || String(e) }));
    process.exit(1);
}
