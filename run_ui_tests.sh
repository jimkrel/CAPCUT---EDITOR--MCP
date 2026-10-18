#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Tạo thư mục tạm cho test drafts
TEMP_DRAFTS_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t 'capcut_drafts')
echo "[1/4] Tạo thư mục test tạm thời: $TEMP_DRAFTS_DIR"

# Copy fixture draft sang thư mục tạm
cp -r "$SCRIPT_DIR/tests/fixtures/sample_draft" "$TEMP_DRAFTS_DIR/sample_draft"

# Thiết lập biến môi trường
export CAPCUT_DRAFTS_DIR="$TEMP_DRAFTS_DIR"
export PYTHONUNBUFFERED=1

echo "[2/4] Khởi động CapCut Web Studio Server..."
python server.py > "$TEMP_DRAFTS_DIR/server.log" 2>&1 &
SERVER_PID=$!

cleanup() {
    echo "[4/4] Dọn dẹp tiến trình server và thư mục tạm..."
    if [ -n "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    rm -rf "$TEMP_DRAFTS_DIR"
}
trap cleanup EXIT INT TERM

# Đợi server sẵn sàng trên port 8765
echo "Đang đợi server khởi động trên port 8765..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8765/api/capcut-status >/dev/null 2>&1; then
        echo "Server đã sẵn sàng!"
        break
    fi
    sleep 0.5
done

echo "[3/4] Chạy toàn bộ UI tests..."
pytest tests/ui/ -v

echo "=== TẤT CẢ UI TEST ĐÃ HOÀN THÀNH XUẤT SẮC ==="
