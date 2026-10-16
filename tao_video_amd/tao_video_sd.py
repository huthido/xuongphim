"""Tạo video clip ngắn bằng stable-diffusion.cpp (sd-cli): chạy trên Windows, Linux, macOS; GPU AMD, Intel, NVIDIA
(Vulkan) hoặc Apple (Metal). Chỉ cần Python 3.9+ (thư viện chuẩn) và ffmpeg. Xem HUONG_DAN_CAI_TAO_VIDEO_AMD.md.

  python tao_video_sd.py --anh nhan_vat.png --prompt "..." --out clip.mp4      Wan2.2 5B, video từ ảnh (mặc định)
  python tao_video_sd.py --prompt "..." --out clip.mp4                          Wan2.2 5B, video từ lời mô tả
  python tao_video_sd.py --mo-hinh wan21 --prompt "..." --out clip.mp4          Wan2.1 1.3B (nhẹ hơn, kém hơn)
  python tao_video_sd.py --jobs viec.json   danh sách {"prompt", "out", "anh"?, "w"?, "h"?, "frames"?, "seed"?};
                                            clip đã có thì bỏ qua trừ khi thêm --overwrite

Mặc định wan22: 640x352, 121 khung, 24 khung/giây (5 giây); wan21: 832x480, 33 khung, 16 khung/giây.
Ảnh vào tự được thu nhỏ và cắt giữa cho đúng cỡ. Lời mô tả viết bằng tiếng Anh.
  --cpu         chạy bằng CPU (rất chậm, chỉ để thử)
  --vae-day-du  giải mã bằng VAE gốc thay cho TAEHV; với wan22 trên GPU chung bộ nhớ (Iris Xe) từng làm GPU bị ngắt
  --extra "..." tham số thêm cho sd-cli, ví dụ --extra "--offload-to-cpu" khi GPU báo thiếu bộ nhớ
sd-cli tìm ở sd/sd-cli(.exe) cạnh script, hoặc đặt biến môi trường SD_CLI.
  --diffusion, --t5, --tae  dùng tệp mô hình khác (danh mục ở <ROOT>/xuong_phim/mo_hinh.json)
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = HERE / "models"
LORA = "Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32"

MO_HINH = {
    # cạnh phải chia hết cho 32 (VAE nén 16 lần, rồi gộp 2x2) với wan22, 16 với wan21
    "wan22": dict(w=640, h=352, frames=121, fps=24, buoc_canh=32, flow_shift="5.0",
                  diffusion=M / "wan22" / "Wan2_2-TI2V-5B-Turbo-Q4_K_M.gguf",
                  tae=M / "wan22" / "taew2_2.safetensors", vae=M / "wan22" / "wan2.2_vae.safetensors"),
    "wan21": dict(w=832, h=480, frames=33, fps=16, buoc_canh=16, flow_shift="3.0",
                  diffusion=M / "wan2.1_t2v_1.3B_fp16.safetensors",
                  tae=M / "taew2_1.safetensors", vae=M / "wan_2.1_vae.safetensors"),
}
T5 = M / "umt5-xxl-encoder-Q5_K_M.gguf"


def tim_ffmpeg():
    p = shutil.which("ffmpeg")
    if not p and sys.platform == "win32":  # winget cài vào đây nhưng PATH chỉ có hiệu lực ở cửa sổ mới
        goc = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        p = next((str(x) for x in goc.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe")), None)
    if not p:
        sys.exit("khong tim thay ffmpeg (Windows: winget install --id Gyan.FFmpeg -e; macOS: brew install ffmpeg; "
                 "Linux: sudo apt install ffmpeg)")
    return p


def tim_sd():
    p = os.environ.get("SD_CLI") or str(HERE / "sd" / ("sd-cli.exe" if sys.platform == "win32" else "sd-cli"))
    if not Path(p).is_file():
        sys.exit(f"khong tim thay sd-cli: {p}")
    return p


def giu_may_thuc(pid):
    """Không cho máy tự ngủ khi để yên trong lúc chạy (gập nắp vẫn ngủ). Trả về tiến trình phụ cần dừng, nếu có."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    elif sys.platform == "darwin" and shutil.which("caffeinate"):
        return subprocess.Popen(["caffeinate", "-i", "-w", str(pid)])
    elif shutil.which("systemd-inhibit"):
        return subprocess.Popen(["systemd-inhibit", "--what=idle:sleep", "--who=tao_video_sd", "--why=dang tao video",
                                 "--mode=block", "sleep", "infinity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mo-hinh", default="wan22", choices=list(MO_HINH))
    ap.add_argument("--anh", help="ảnh khung đầu (chỉ wan22)")
    ap.add_argument("--prompt", help="mô tả clip, viết bằng tiếng Anh")
    ap.add_argument("--out", help="file video ra (.mp4)")
    ap.add_argument("--jobs", help="file JSON chứa danh sách việc")
    ap.add_argument("--w", type=int)
    ap.add_argument("--h", type=int)
    ap.add_argument("--frames", type=int, help="số khung hình; tự làm tròn về dạng 4k+1")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--vae-day-du", action="store_true")
    ap.add_argument("--extra", default="", help="tham số thêm cho sd-cli, trong một chuỗi")
    ap.add_argument("--diffusion", help="tệp mô hình chính thay cho mặc định (vd bản Q6_K, Q8_0 trong mo_hinh.json)")
    ap.add_argument("--t5", help="tệp bộ mã hoá chữ umT5 thay cho mặc định")
    ap.add_argument("--tae", help="tệp bộ giải mã nhanh TAEHV thay cho mặc định")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    if a.jobs:
        jobs = json.loads(Path(a.jobs).read_text(encoding="utf-8-sig"))
    elif a.prompt and a.out:
        jobs = [{"prompt": a.prompt, "out": a.out, "anh": a.anh}]
    else:
        ap.error("cần --prompt và --out, hoặc --jobs")
    jobs = [j for j in jobs if a.overwrite or not Path(j["out"]).exists()]
    if not jobs:
        print("khong con clip nao phai tao"); return

    cfg = dict(MO_HINH[a.mo_hinh])
    for k in ("diffusion", "tae"):
        if getattr(a, k):
            cfg[k] = Path(getattr(a, k))
    t5 = Path(a.t5) if a.t5 else T5
    thieu = [str(p) for p in (cfg["diffusion"], t5, cfg["vae"] if a.vae_day_du else cfg["tae"]) if not p.is_file()]
    if thieu:
        sys.exit("thieu file mo hinh:\n  " + "\n  ".join(thieu))
    sd, ffmpeg = tim_sd(), tim_ffmpeg()
    phu = giu_may_thuc(os.getpid())
    for cu in Path(tempfile.gettempdir()).glob("tao_video_sd_*"):  # thư mục tạm sót lại khi bị huỷ giữa chừng
        if time.time() - cu.stat().st_mtime > 6 * 3600:
            shutil.rmtree(cu, ignore_errors=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="tao_video_sd_"))
    try:
        for j in jobs:
            w, h = int(j.get("w") or a.w or cfg["w"]), int(j.get("h") or a.h or cfg["h"])
            b = cfg["buoc_canh"]
            gw, gh = -(-w // b) * b, -(-h // b) * b
            n = int(j.get("frames") or a.frames or cfg["frames"])
            n = max(5, (n - 1) // 4 * 4 + 1)
            fps = int(j.get("fps") or a.fps or cfg["fps"])
            seed = int(j.get("seed", a.seed))
            out = Path(j["out"]).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            webm = tmpdir / "ra.webm"

            prompt = j["prompt"].replace('"', "'")
            if a.mo_hinh == "wan21":
                prompt += f"<lora:{LORA}:0.95>"
            cmd = [sd, "-M", "vid_gen", "--diffusion-model", str(cfg["diffusion"]), "--t5xxl", str(t5),
                   "-p", prompt, "-W", str(gw), "-H", str(gh), "--video-frames", str(n), "--fps", str(fps),
                   "--cfg-scale", "1.0", "--sampling-method", "euler", "--steps", str(a.steps),
                   "--flow-shift", cfg["flow_shift"], "--seed", str(seed), "-o", str(webm)]
            if a.mo_hinh == "wan21":
                cmd += ["--lora-model-dir", str(M / "loras"), "--vae-tiling"]
            cmd += ["--vae", str(cfg["vae"])] if a.vae_day_du else ["--tae", str(cfg["tae"])]
            anh = j.get("anh")
            if anh:
                if a.mo_hinh != "wan21":
                    vao = tmpdir / "vao.png"  # thu nhỏ phủ kín rồi cắt giữa cho đúng cỡ khung
                    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(anh), "-vf",
                                    f"scale={gw}:{gh}:force_original_aspect_ratio=increase,crop={gw}:{gh}",
                                    "-frames:v", "1", str(vao)], check=True)
                    cmd += ["-i", str(vao)]
                else:
                    print("canh bao: wan21 khong nhan anh vao, bo qua --anh", flush=True)
            if a.cpu:
                cmd += ["--backend", "cpu"]
            cmd += shlex.split(a.extra)

            print(f"== {out.name}: {a.mo_hinh} {w}x{h} {n} khung {fps} khung/giay seed {seed}"
                  + (f" anh {Path(anh).name}" if anh else ""), flush=True)
            t = time.time()
            r = subprocess.run(cmd)
            if r.returncode != 0 or not webm.exists():
                sys.exit(f"sd-cli loi (ma {r.returncode}) khi tao {out}")
            subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(webm), "-vf", f"crop={w}:{h}", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(out)], check=True)
            webm.unlink()
            print(f"OK {out}  {w}x{h}  {n} khung = {n / fps:.1f}s  {time.time() - t:.0f}s", flush=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if phu:
            phu.terminate()


if __name__ == "__main__":
    main()
