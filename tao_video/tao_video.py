"""Tạo video clip ngắn từ lời mô tả bằng Wan2.1-T2V-1.3B (OpenVINO int4, chưng cất CausVid 4 bước). Xem HUONG_DAN_CAI_TAO_VIDEO.md.

  env python: <ROOT>\\tao_video\\env\\Scripts\\python.exe -I <ROOT>\\tao_video\\tao_video.py ...

  Một clip:   --prompt "..." --out clip.mp4 [--w 832 --h 480] [--frames 33] [--fps 16] [--seed 7]
  Nhiều clip: --jobs viec.json   (danh sách {"prompt", "out", "w"?, "h"?, "frames"?, "seed"?};
              mô hình chỉ nạp một lần, clip đã có thì bỏ qua trừ khi thêm --overwrite)
"""
import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # kênh Xet của Hugging Face trả lỗi 401 trên máy gốc
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402
from diffusers import AutoencoderKLWan  # noqa: E402
from diffusers.utils import export_to_video  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402

from ov_wan_helper import OVWanPipeline  # noqa: E402

MODEL = "liuming9157/Wan2.1-T2V-1.3B-Diffusers-ov-int4"
REVISION = "821bbdc4313add7f129deecbf5e56ef682df752d"
# Bộ giải mã OpenVINO trong MODEL bị cố định 5 khung ẩn (= 17 khung hình) lúc chuyển đổi, nên không dùng.
# Mặc định giải mã bằng TAEHV (taehv.py + taew2_1.safetensors cạnh script, MIT): nhanh gấp ~20 lần VAE gốc,
# hình gần như giống hệt. --vae-day-du dùng VAE gốc của Wan (PyTorch, CPU): đúng nhất nhưng rất chậm.
VAE = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
VAE_REVISION = "0fad780a534b6463e45facd96134c9f345acfa5b"


def tai(repo, rev, **kw):
    try:
        return snapshot_download(repo, revision=rev, local_files_only=True, **kw)
    except Exception:
        return snapshot_download(repo, revision=rev, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", help="mô tả clip, viết bằng tiếng Anh")
    ap.add_argument("--out", help="file video ra (.mp4)")
    ap.add_argument("--jobs", help="file JSON chứa danh sách việc")
    ap.add_argument("--w", type=int, default=832)
    ap.add_argument("--h", type=int, default=480)
    ap.add_argument("--frames", type=int, default=33, help="số khung hình; tự làm tròn về dạng 4k+1")
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--dev", default="gpu", choices=["gpu", "cpu"])
    ap.add_argument("--vae-day-du", action="store_true", help="giải mã bằng VAE gốc của Wan (chậm hơn ~20 lần)")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    if a.jobs:
        jobs = json.loads(Path(a.jobs).read_text(encoding="utf-8-sig"))
    elif a.prompt and a.out:
        jobs = [{"prompt": a.prompt, "out": a.out}]
    else:
        ap.error("cần --prompt và --out, hoặc --jobs")
    jobs = [j for j in jobs if a.overwrite or not Path(j["out"]).exists()]
    if not jobs:
        print("khong con clip nao phai tao"); return

    # Giữ máy không tự ngủ khi để yên trong lúc chạy (Windows Modern Standby từng làm tiến trình chết giữa chừng).
    # Không chặn được khi gập nắp. Hết tác dụng khi tiến trình kết thúc.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

    # Ba giai đoạn, xong giai đoạn nào thì bỏ mô hình đó khỏi RAM (máy 16 GB dùng chung với GPU):
    # 1) mã hoá lời mô tả (umT5, 3,6 GB)  2) tạo chuyển động (transformer)  3) giải mã khung hình (VAE).
    cache = HERE / "ov_cache"
    cache.mkdir(exist_ok=True)
    t = time.time()
    dev = a.dev.upper()
    pipe = OVWanPipeline(Path(tai(MODEL, REVISION)), {"transformer": dev, "text_encoder": dev, "vae": "CPU"},
                         ov_config={"CACHE_DIR": str(cache)})
    print(f"nap mo hinh ({a.dev}): {time.time() - t:.0f}s", flush=True)

    embeds = [pipe.encode_prompt(prompt=j["prompt"], do_classifier_free_guidance=False, max_sequence_length=512)[0]
              for j in jobs]
    pipe.text_encoder = None
    gc.collect()

    latents = []
    for j, e in zip(jobs, embeds):
        w, h = int(j.get("w", a.w)), int(j.get("h", a.h))
        gw, gh = -(-w // 16) * 16, -(-h // 16) * 16  # mô hình cần cạnh chia hết cho 16
        t = time.time()
        latents.append(pipe(prompt_embeds=e, height=gh, width=gw, num_frames=int(j.get("frames", a.frames)),
                            guidance_scale=1.0, num_inference_steps=a.steps, output_type="latent",
                            generator=torch.Generator().manual_seed(int(j.get("seed", a.seed)))).frames)
        j["_tao"] = time.time() - t
    processor = pipe.video_processor
    mean = torch.tensor(pipe.latents_mean).view(1, -1, 1, 1, 1)
    std = torch.tensor(pipe.latents_std).view(1, -1, 1, 1, 1)
    del pipe
    gc.collect()

    if a.vae_day_du:
        vae = AutoencoderKLWan.from_pretrained(tai(VAE, VAE_REVISION, allow_patterns=["vae/*"]), subfolder="vae",
                                               torch_dtype=torch.float32)
    else:
        from taehv import TAEHV
        tae = TAEHV(str(HERE / "taew2_1.safetensors"))
    for j, z in zip(jobs, latents):
        w, h = int(j.get("w", a.w)), int(j.get("h", a.h))
        t = time.time()
        with torch.no_grad():
            if a.vae_day_du:
                frames = processor.postprocess_video(vae.decode(z * std + mean).sample, output_type="np")[0]
            else:  # TAEHV nhận khung ẩn chưa khử chuẩn hoá, dạng NTCHW, trả về [0, 1]
                v = tae.decode_video(z.transpose(1, 2), parallel=True, show_progress_bar=False)
                frames = v[0].permute(0, 2, 3, 1).clamp(0, 1).numpy()
        gh, gw = frames.shape[1:3]
        if (gw, gh) != (w, h):
            x, y = (gw - w) // 2, (gh - h) // 2
            frames = frames[:, y:y + h, x:x + w]
        out = Path(j["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        export_to_video(list(frames), str(out), fps=a.fps, macro_block_size=1)
        print(f"OK {out}  {w}x{h}  {len(frames)} khung = {len(frames) / a.fps:.1f}s  "
              f"tao chuyen dong {j['_tao']:.0f}s, giai ma {time.time() - t:.0f}s", flush=True)

if __name__ == "__main__":
    main()
