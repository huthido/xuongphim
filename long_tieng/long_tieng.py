"""Lồng tiếng tiếng Việt cho phim bằng VieNeu-TTS v3 Turbo (CPU, không cần GPU). Xem HUONG_DAN_CAI_LAM_PHIM.md.

  <ROOT>/long_tieng/env/Scripts/python.exe -I <ROOT>/long_tieng/long_tieng.py --loi loi.json --out <thư mục>
  ... --giong                 liệt kê giọng có sẵn

loi.json là danh sách {"ten": "n01", "giong": "Ngọc Linh", "cau": "...", "cao_do": 0}
  ten     tên file ra (<ten>.mp3)
  giong   tên giọng có sẵn (xem --giong); bỏ trống thì dùng giọng mặc định
  cao_do  số nửa cung nâng (+) hoặc hạ (-) giọng, giữ nguyên tốc độ; ví dụ 3 cho giọng trẻ em. Mặc định 0
File đã có thì bỏ qua (xoá file để tạo lại). In ra độ dài từng câu để đặt vào phim.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--loi", help="file JSON danh sách câu")
    ap.add_argument("--out", help="thư mục ghi file .mp3")
    ap.add_argument("--giong", action="store_true", help="liệt kê giọng có sẵn rồi thoát")
    a = ap.parse_args()
    if not a.giong and not (a.loi and a.out):
        ap.error("cần --loi và --out, hoặc --giong")

    from vieneu import Vieneu  # nạp chậm (~20 giây), lần đầu tải mô hình về bộ đệm Hugging Face

    t = time.time()
    tts = Vieneu()
    print(f"nap mo hinh: {time.time() - t:.0f}s", flush=True)
    if a.giong:
        for nhan, ma in tts.list_preset_voices():
            print(f"{ma} | {nhan}")
        return

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for dong in json.loads(Path(a.loi).read_text(encoding="utf-8-sig")):
        mp3 = out / f"{dong['ten']}.mp3"
        if mp3.exists():
            continue
        t = time.time()
        kw = {"voice": dong["giong"]} if dong.get("giong") else {}
        wav = out / f"{dong['ten']}.tmp.wav"
        tts.save(tts.infer(dong["cau"], **kw), str(wav))
        cao_do = float(dong.get("cao_do", 0))
        loc = []
        if cao_do:  # đổi cao độ, giữ tốc độ: tăng tần số lấy mẫu rồi kéo dài lại
            r = 2 ** (cao_do / 12)
            sr = int(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate", "-of", "csv=p=0",
                                     str(wav)], capture_output=True, text=True, check=True).stdout.strip())
            loc = ["-af", f"asetrate={sr}*{r:.5f},aresample={sr},atempo={1 / r:.5f}"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), *loc, "-b:a", "128k", str(mp3)], check=True)
        wav.unlink()
        dai = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(mp3)], capture_output=True, text=True, check=True).stdout)
        print(f"{dong['ten']}  {dai:.2f}s  (sinh {time.time() - t:.1f}s)  {dong['cau']}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
