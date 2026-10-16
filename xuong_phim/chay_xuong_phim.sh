#!/bin/sh
# Mở Xưởng phim trên macOS / Linux: ./chay_xuong_phim.sh   (lần đầu: chmod +x chay_xuong_phim.sh)
cd "$(dirname "$0")" || exit 1
for PY in ../long_tieng/env/bin/python ../tao_video/env/bin/python python3 python; do
  if command -v "$PY" >/dev/null 2>&1 || [ -x "$PY" ]; then
    exec "$PY" -I xuong_phim.py "$@"
  fi
done
echo "Khong tim thay Python 3.9+ (macOS: brew install python; Ubuntu: sudo apt install python3)"
exit 1
