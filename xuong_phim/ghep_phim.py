"""Ghép các clip thành một phim: mỗi cảnh một clip, kèm lời thoại (nếu có), thêm nhạc nền (nếu có).
Chỉ cần Python 3.9+ (thư viện chuẩn) và ffmpeg; chạy trên Windows, Linux, macOS.

  python ghep_phim.py --jobs phim.json

phim.json: {"out": "phim.mp4", "w": 1280, "h": 720, "fps": 24,
            "canh": [{"video": "c1.mp4", "tieng": "c1.mp3", "tre": 0.3, "bo_dau": 0}, ...],
            "nhac": "nhac.mp3", "am_luong_nhac": 0.15}
  tre      số giây sau khi cảnh bắt đầu thì lời thoại cất lên
  bo_dau   cắt bỏ bao nhiêu giây đầu clip (đầu clip đôi khi giật)
Lời thoại dài hơn clip thì khung cuối được giữ lại cho đến khi nói xong.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tao_video_amd"))
try:
    from tao_video_sd import tim_ffmpeg
except ImportError:  # dùng riêng ghep_phim.py, không có thư mục tao_video_amd
    def tim_ffmpeg():
        p = shutil.which("ffmpeg")
        if not p:
            sys.exit("khong tim thay ffmpeg")
        return p


def co_khung(ffprobe, p):
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def do_dai(ffprobe, p):
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", required=True)
    a = ap.parse_args()
    job = json.loads(Path(a.jobs).read_text(encoding="utf-8-sig"))
    ffmpeg = tim_ffmpeg()
    ffprobe = str(Path(ffmpeg).with_name(Path(ffmpeg).name.replace("ffmpeg", "ffprobe")))
    w, h, fps = int(job.get("w", 1280)), int(job.get("h", 720)), int(job.get("fps", 24))
    canh = job["canh"]
    if not canh:
        sys.exit("chua co canh nao")
    out = Path(job["out"]).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    for cu in Path(tempfile.gettempdir()).glob("ghep_phim_*"):  # thư mục tạm sót lại khi bị huỷ giữa chừng
        if time.time() - cu.stat().st_mtime > 6 * 3600:
            shutil.rmtree(cu, ignore_errors=True)
    tmp = Path(tempfile.mkdtemp(prefix="ghep_phim_"))
    t0 = time.time()
    try:
        ds = []
        for i, c in enumerate(canh, 1):
            bo = float(c.get("bo_dau") or 0)
            tre = float(c.get("tre") or 0)
            dv = do_dai(ffprobe, c["video"]) - bo
            dt = do_dai(ffprobe, c["tieng"]) if c.get("tieng") else 0
            d = max(dv, tre + dt + 0.4) if dt else dv
            cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{bo:.3f}", "-i", str(c["video"])]
            cw, ch = co_khung(ffprobe, c["video"])
            if abs((cw / ch) / (w / h) - 1) < 0.1:  # gần cùng tỉ lệ (640x352 vào 16:9): phóng kín rồi cắt mép
                khop = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            else:  # khác hẳn tỉ lệ (clip dọc trong phim ngang): thu vừa rồi thêm viền đen
                khop = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            vf = f"[0:v]{khop},setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={d:.3f}[v]"
            if dt:
                cmd += ["-i", str(c["tieng"])]
                af = f"[1:a]aresample=48000,aformat=channel_layouts=stereo,adelay={int(tre * 1000)}:all=1,apad[a]"
            else:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                af = "[1:a]anull[a]"
            seg = tmp / f"canh_{i:03d}.mp4"
            cmd += ["-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", str(seg)]
            subprocess.run(cmd, check=True)
            ds.append(d)
            print(f"canh {i}/{len(canh)}  {d:.2f}s  {Path(c['video']).name}"
                  + (f" + {Path(c['tieng']).name}" if dt else ""), flush=True)

        ds_file = tmp / "ds.txt"
        ds_file.write_text("".join(f"file '{tmp / f'canh_{i:03d}.mp4'}'\n".replace("\\", "/")
                                   for i in range(1, len(canh) + 1)), encoding="utf-8")
        noi = tmp / "noi.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(ds_file), "-c", "copy",
                        str(noi)], check=True)
        tong = sum(ds)
        if job.get("nhac"):
            vol = float(job.get("am_luong_nhac", 0.15))
            mo = max(0.0, tong - 2)
            subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(noi), "-stream_loop", "-1", "-i", str(job["nhac"]),
                            "-filter_complex",
                            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},"
                            f"afade=t=out:st={mo:.2f}:d=2[n];[0:a][n]amix=inputs=2:duration=first:normalize=0[a]",
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-t", f"{tong:.3f}", "-movflags", "+faststart", str(out)], check=True)
        else:
            subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(noi), "-c", "copy", "-movflags", "+faststart",
                            str(out)], check=True)
        print(f"OK {out}  {w}x{h}  {len(canh)} canh = {tong:.1f}s  {time.time() - t0:.0f}s", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
