"""Trình cài của Xưởng phim: kiểm tra máy, đề xuất mô hình hợp với máy, tải và kiểm tra mô hình, dựng môi trường
lồng tiếng, bật tự chạy khi mở máy. Chỉ cần Python 3.9+ (thư viện chuẩn); chạy trên Windows, Linux, macOS.
Giao diện (thẻ Thiết lập) và MCP đều gọi tệp này; agent cũng có thể chạy trực tiếp.

  python cai_dat.py kiem_may [--json]          cấu hình máy + mô hình đề xuất
  python cai_dat.py de_xuat                    cài đúng theo đề xuất (sd-cli, mô hình, lồng tiếng) và đặt làm mặc định
  python cai_dat.py sd_cli [--ban vulkan|cpu|cuda|rocm|metal]
  python cai_dat.py mo_hinh <id> [<id>...] [--mac_dinh] [--w 640 --h 352]   id trong mo_hinh.json
  python cai_dat.py long_tieng                 môi trường VieNeu (dùng uv nếu có, không thì venv + pip)
  python cai_dat.py tu_khoi_dong bat|tat       Xưởng phim tự chạy nền khi đăng nhập máy (để PWA luôn mở được)
  python cai_dat.py kiem                       kiểm tra những gì đã cài

Tệp tải về: <ROOT>/tao_video_amd/sd và <ROOT>/tao_video_amd/models. Bị ngắt thì chạy lại cùng lệnh, tải tiếp
phần còn thiếu. Mỗi tệp được so kích thước và SHA256 với mo_hinh.json.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent
GOC = Path(os.environ.get("XUONG_PHIM_GOC") or APP.parent).resolve()
SD = GOC / "tao_video_amd" / "sd"
MODELS = GOC / "tao_video_amd" / "models"
LT = GOC / "long_tieng"
CAU_HINH = APP / "cau_hinh.json"
WIN, MAC = sys.platform == "win32", sys.platform == "darwin"
HO_HANG = {"wan22": 2, "wan21": 1}
DM = json.loads((APP / "mo_hinh.json").read_text(encoding="utf-8"))


def in_(*a):
    print(*a, flush=True)


def sd_cli_path():
    p = os.environ.get("SD_CLI")
    return Path(p) if p else SD / ("sd-cli.exe" if WIN else "sd-cli")


def py_env(thu_muc):
    p = thu_muc / ("Scripts/python.exe" if WIN else "bin/python")
    return p if p.is_file() else None


# ---------- kiểm tra máy ----------

def _chay(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=0x08000000 if WIN else 0)
        return r.stdout + r.stderr
    except Exception:
        return ""


def _ram():
    try:
        if WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tong", ctypes.c_ulonglong),
                            ("con", ctypes.c_ulonglong)] + [(f"x{i}", ctypes.c_ulonglong) for i in range(5)]
            s = MS()
            s.len = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.tong / 2 ** 30, s.con / 2 ** 30
        if MAC:
            tong = int(_chay(["sysctl", "-n", "hw.memsize"]).strip() or 0) / 2 ** 30
            return tong, None
        d = dict((l.split(":")[0], int(l.split()[1])) for l in Path("/proc/meminfo").read_text().splitlines())
        tong, con = d["MemTotal"] / 2 ** 20, d["MemAvailable"] / 2 ** 20
        try:  # trong container: giới hạn cgroup v2 nhỏ hơn RAM máy thì lấy giới hạn
            gh = Path("/sys/fs/cgroup/memory.max").read_text().strip()
            if gh != "max":
                dung = int(Path("/sys/fs/cgroup/memory.current").read_text())
                tong, con = min(tong, int(gh) / 2 ** 30), min(con, (int(gh) - dung) / 2 ** 30)
        except OSError:
            pass
        return tong, con
    except Exception:
        return None, None


def _cpu():
    if WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            return platform.processor()
    if MAC:
        return _chay(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or platform.machine()
    m = re.search(r"model name\s*:\s*(.+)", Path("/proc/cpuinfo").read_text(errors="ignore")) \
        if Path("/proc/cpuinfo").exists() else None
    return m.group(1).strip() if m else platform.machine()


def _gpu():
    """Danh sách {ten, vram_gb (None = dùng chung RAM), uma, hang}."""
    ds = []
    if WIN:
        try:
            import winreg
            goc = r"SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, goc) as h:
                i = 0
                while True:
                    try:
                        s = winreg.EnumKey(h, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(h, s) as g:
                            ten = winreg.QueryValueEx(g, "DriverDesc")[0]
                            vram = None
                            for khoa in ("HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize"):
                                try:
                                    v = winreg.QueryValueEx(g, khoa)[0]
                                    vram = (int.from_bytes(v, "little") if isinstance(v, bytes) else int(v)) / 2 ** 30
                                    break
                                except OSError:
                                    pass
                    except OSError:
                        continue
                    if re.search(r"Basic Display|Remote|Virtual|Parsec|Meta Virtual", ten, re.I):
                        continue
                    ds.append({"ten": ten, "vram_gb": vram})
        except OSError:
            pass
    elif MAC:
        try:
            d = json.loads(_chay(["system_profiler", "SPDisplaysDataType", "-json"], 30) or "{}")
            for g in d.get("SPDisplaysDataType", []):
                vr = g.get("spdisplays_vram") or g.get("spdisplays_vram_shared") or ""
                m = re.search(r"(\d+)\s*GB", vr)
                ds.append({"ten": g.get("sppci_model") or g.get("_name", "GPU"),
                           "vram_gb": None if platform.machine() == "arm64" else (float(m.group(1)) if m else None)})
        except ValueError:
            pass
    else:
        if shutil.which("nvidia-smi"):
            for l in _chay(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
                if "," in l:
                    ten, mb = l.rsplit(",", 1)
                    ds.append({"ten": ten.strip(), "vram_gb": float(mb) / 1024})
        for c in sorted(Path("/sys/class/drm").glob("card[0-9]")):
            dv = c / "device"
            try:
                vendor = (dv / "vendor").read_text().strip()
            except OSError:
                continue
            if vendor == "0x10de" and ds:
                continue  # đã có từ nvidia-smi
            ten = {"0x1002": "AMD GPU", "0x8086": "Intel GPU", "0x10de": "NVIDIA GPU"}.get(vendor, f"GPU {vendor}")
            vram = None
            try:
                vram = int((dv / "mem_info_vram_total").read_text()) / 2 ** 30
            except OSError:
                pass
            ds.append({"ten": ten, "vram_gb": vram})
    for g in ds:
        t = g["ten"].lower()
        g["hang"] = "nvidia" if "nvidia" in t or "geforce" in t or "rtx" in t else \
            "amd" if "amd" in t or "radeon" in t else "intel" if "intel" in t or " arc" in t else \
            "apple" if "apple" in t else "khac"
        # card tích hợp dùng chung RAM: Windows báo cho chúng một con số nhỏ (Iris Xe: 2 GB) hoặc không báo
        tich_hop = re.search(r"iris|uhd|hd graphics|radeon\(tm\) graphics|radeon graphics|vega \d+ graphics|"
                             r"radeon \d{3}m|apple", t)
        g["uma"] = g["vram_gb"] is None or g["vram_gb"] < 4 or bool(tich_hop and g["hang"] != "nvidia")
    return ds


def _sd_thiet_bi():
    """Thiết bị sd-cli thấy được (nếu đã cài): [{ten, uma}]."""
    p = sd_cli_path()
    if not p.is_file():
        return None
    out = _chay([str(p), "--list-devices"], 60)
    ds = []
    for m in re.finditer(r"ggml_vulkan: \d+ = (.+?) \|.*?uma: (\d)", out):
        ds.append({"ten": m.group(1).strip(), "uma": m.group(2) == "1"})
    if not ds and re.search(r"\bMTL\d|Metal", out):
        ds.append({"ten": "Apple GPU (Metal)", "uma": True})
    return ds


def kiem_may():
    tong, con = _ram()
    gpu = _gpu()
    try:
        o_dia = shutil.disk_usage(MODELS if MODELS.exists() else GOC).free / 2 ** 30
    except OSError:
        o_dia = None
    sd = _sd_thiet_bi()
    if sd and len(sd) == 1 and len(gpu) == 1:  # sd-cli (Vulkan) biết chắc thiết bị có dùng chung RAM hay không
        gpu[0]["uma"] = sd[0]["uma"]
    for g in gpu:
        if g["uma"]:
            g["vram_gb"] = None
        else:
            g["vram_gb"] = round(g["vram_gb"], 1)
    return {"he_dieu_hanh": sys.platform, "kien_truc": platform.machine(), "cpu": _cpu(), "nhan": os.cpu_count(),
            "ram_gb": round(tong, 1) if tong else None, "ram_trong_gb": round(con, 1) if con else None,
            "gpu": gpu, "sd_cli_thay": sd, "o_dia_trong_gb": round(o_dia, 1) if o_dia else None,
            "co_tao_anh": (GOC / "tao_anh.py").is_file() and bool(py_env(GOC / "fastsdcpu" / "env"))}


# ---------- đề xuất ----------

def tep_co(tid):
    t = DM["tep"][tid]
    p = MODELS / t["duong_dan"]
    return p.is_file() and p.stat().st_size == t["co"]


def mo_hinh_da_cai(m):
    return all(tep_co(m[k]) for k in ("diffusion", "t5", "tae", "lora") if m.get(k))


def can_tai(m):
    return sum(DM["tep"][m[k]]["co"] for k in ("diffusion", "t5", "tae", "lora") if m.get(k) and not tep_co(m[k]))


def bo_nho_lam_viec(ho, w, h):
    return DM["bo_nho_lam_viec"]["gb_o_832x480"][ho] * (w * h) / (832 * 480)


def ban_sd_cli(may):
    if MAC:
        return "darwin-metal"
    hang = {g["hang"] for g in may["gpu"]}
    he = "win32" if WIN else "linux"
    if not may["gpu"]:
        return f"{he}-cpu"
    return f"{he}-vulkan"  # Vulkan chạy được trên AMD, Intel, NVIDIA; đã thử trên Intel Iris Xe


def ngan_sach(may):
    """(GB dành cho mô hình + làm việc, mô tả, có GPU riêng không)."""
    rieng = [g for g in may["gpu"] if not g["uma"]]
    ram = may["ram_gb"] or 8
    if rieng:
        g = max(rieng, key=lambda g: g["vram_gb"])
        return g["vram_gb"] * 0.9, f"GPU rời {g['ten']} {g['vram_gb']:.0f} GB", True, ram
    if may["gpu"]:
        # card tích hợp dùng chung RAM: Windows/Linux đẩy bớt ứng dụng khác ra bộ nhớ ảo. Hệ số 0,95 chỉnh theo máy
        # gốc (15,6 GB): chạy được Wan2.2 Q4 ở 640x352 (mô hình 7,3 + làm việc 6,8 GB), không chạy được 832x480
        return ram * (0.75 if MAC else 0.95), f"GPU tích hợp {may['gpu'][0]['ten']} dùng chung {ram:.0f} GB RAM", False, ram
    return ram * 0.8, f"không thấy GPU, chạy bằng CPU ({ram:.0f} GB RAM)", False, ram


def de_xuat(may=None):
    may = may or kiem_may()
    ns, mo_ta, rieng, ram = ngan_sach(may)
    canh_bao, phuong_an = [], []
    for m in sorted(DM["video"], key=lambda m: -m["chat_luong"]):
        for w, h in DM["kich_thuoc"][m["ho"]]:
            can = m["bo_nho_gb"] + bo_nho_lam_viec(m["ho"], w, h)
            extra = []
            if can > ns and rieng and can <= ns + ram * 0.5:
                extra = ["--offload-to-cpu"]  # GPU rời thiếu bộ nhớ: để trọng số ở RAM, nạp dần lên GPU
            if can <= ns or extra:
                phuong_an.append({"id": m["id"], "ten": m["ten"], "ho": m["ho"], "w": w, "h": h, "can_gb": round(can, 1),
                                  "extra": extra, "da_thu": m["da_thu"], "chat_luong": m["chat_luong"],
                                  "can_tai_gb": round(can_tai(m) / 2 ** 30, 1), "da_cai": mo_hinh_da_cai(m)})
    # họ mô hình quan trọng nhất (Wan2.2 giữ mặt nhân vật, Wan2.1 thì không), rồi khung lớn, rồi bản nén ít mất mát,
    # rồi không cần offload
    phuong_an.sort(key=lambda p: (-HO_HANG[p["ho"]], -p["w"] * p["h"], -p["chat_luong"], bool(p["extra"])))
    chon = phuong_an[0] if phuong_an else None
    if not chon:
        canh_bao.append("Máy không đủ bộ nhớ cho mô hình video nào; vẫn dùng được lồng tiếng và ghép phim.")
    if not may["gpu"]:
        canh_bao.append("Không có GPU: tạo video bằng CPU rất chậm (chưa đo), có thể mất hàng giờ mỗi clip.")
    if chon and not chon["da_thu"]:
        canh_bao.append(f"{chon['ten']} chưa chạy thử thật; số bộ nhớ là ước lượng. Nếu lỗi thiếu bộ nhớ, chọn "
                        f"phương án kế tiếp.")
    if chon and may["o_dia_trong_gb"] is not None and chon["can_tai_gb"] + 1 > may["o_dia_trong_gb"]:
        canh_bao.append(f"Ổ đĩa còn {may['o_dia_trong_gb']} GB, cần tải {chon['can_tai_gb']} GB.")
    if (may["ram_gb"] or 0) < 4:
        canh_bao.append("RAM dưới 4 GB: lồng tiếng VieNeu có thể không chạy.")
    return {"may": may, "ngan_sach_gb": round(ns, 1), "ngan_sach_mo_ta": mo_ta, "sd_cli_ban": ban_sd_cli(may),
            "video": chon, "phuong_an_khac": phuong_an[1:6], "canh_bao": canh_bao,
            "tieng": "VieNeu (chạy CPU, mọi máy từ 4 GB RAM)",
            "anh": "FLUX.2 klein (OpenVINO)" if may["co_tao_anh"] else "chưa có công cụ tạo ảnh cho máy này: "
                                                                     "tải ảnh nhân vật lên thay thế"}


def doc_cau_hinh():
    try:
        return json.loads(CAU_HINH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def luu_cau_hinh(**kw):
    c = doc_cau_hinh()
    c.update(kw, luc=time.strftime("%Y-%m-%d %H:%M"))
    CAU_HINH.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- tải ----------

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for khuc in iter(lambda: f.read(1 << 22), b""):
            h.update(khuc)
    return h.hexdigest()


def tai(url, dich, co=None, sha=None):
    dich = Path(dich)
    dich.parent.mkdir(parents=True, exist_ok=True)
    if dich.is_file() and (co is None or dich.stat().st_size == co):
        in_(f"da co  {dich.name}")
        return
    if co and shutil.disk_usage(dich.parent).free < co - (dich.with_name(dich.name + ".part").stat().st_size
                                                          if dich.with_name(dich.name + ".part").exists() else 0):
        raise SystemExit(f"o dia khong du cho {dich.name} ({co / 2 ** 30:.1f} GB)")
    part = dich.with_name(dich.name + ".part")
    da = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "xuong-phim-cai-dat/1", **({"Range": f"bytes={da}-"} if da else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        if da and r.status != 206:  # máy chủ không cho tải tiếp: tải lại từ đầu
            da = 0
        tong = co or (da + int(r.headers.get("Content-Length") or 0))
        t0, moc, n = time.time(), 0, da
        with open(part, "ab" if da else "wb") as f:
            while True:
                khuc = r.read(1 << 20)
                if not khuc:
                    break
                f.write(khuc)
                n += len(khuc)
                pt = int(n * 100 / tong) if tong else 0
                if pt >= moc + 5 or not khuc:
                    moc = pt
                    toc = (n - da) / max(time.time() - t0, 0.1) / 2 ** 20
                    in_(f"tai   {dich.name} {pt}% ({n / 2 ** 30:.2f}/{tong / 2 ** 30:.2f} GB) {toc:.1f} MB/s")
    if co and part.stat().st_size != co:
        raise SystemExit(f"{dich.name}: tai thieu ({part.stat().st_size} / {co} byte); chay lai lenh de tai tiep")
    if sha:
        in_(f"kiem  {dich.name} sha256...")
        if sha256(part) != sha:
            part.unlink()
            raise SystemExit(f"{dich.name}: SHA256 khong khop, da xoa; chay lai de tai lai")
    part.replace(dich)
    in_(f"xong  {dich.name}")


def cai_sd_cli(ban=None):
    p = sd_cli_path()
    if p.is_file():
        in_(f"da co  sd-cli: {p}")
        return
    if not ban:
        ban = ban_sd_cli(kiem_may())
    elif "-" not in ban:
        ban = f"{'darwin' if MAC else 'win32' if WIN else 'linux'}-{ban}"
    if ban not in DM["sd_cli"]["goi"]:
        raise SystemExit(f"khong co ban sd-cli {ban}; co: {', '.join(DM['sd_cli']['goi'])}")
    ten, sha = DM["sd_cli"]["goi"][ban]
    z = SD.parent / ten
    tai(DM["sd_cli"]["url"] + ten, z, sha=sha)
    SD.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as f:
        f.extractall(SD)
    z.unlink()
    exe = next(SD.rglob("sd-cli.exe" if WIN else "sd-cli"), None)
    if not exe:
        raise SystemExit("goi sd-cli khong co tep sd-cli")
    if exe.parent != SD:  # gói để trong thư mục con: chuyển lên sd/
        for x in exe.parent.iterdir():
            shutil.move(str(x), str(SD / x.name))
    if not WIN:
        for x in SD.iterdir():
            if x.is_file():
                x.chmod(x.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if MAC:
        _chay(["xattr", "-dr", "com.apple.quarantine", str(SD)])
    in_(f"xong  sd-cli {ban}")
    in_(_chay([str(sd_cli_path()), "--list-devices"], 60).strip()[-1500:])


def cai_mo_hinh(ids, mac_dinh=False, w=None, h=None):
    ds = {m["id"]: m for m in DM["video"]}
    for i in ids:
        if i not in ds:
            raise SystemExit(f"khong co mo hinh {i}; co: {', '.join(ds)}")
        m = ds[i]
        in_(f"== {m['ten']}: can tai {can_tai(m) / 2 ** 30:.1f} GB")
        for k in ("t5", "tae", "lora", "diffusion"):
            if m.get(k):
                t = DM["tep"][m[k]]
                tai(t["url"], MODELS / t["duong_dan"], t["co"], t["sha256"])
    if mac_dinh and ids:
        m = ds[ids[0]]
        w, h = w or DM["kich_thuoc"][m["ho"]][-1][0], h or DM["kich_thuoc"][m["ho"]][-1][1]
        luu_cau_hinh(video={"id": m["id"], "w": w, "h": h, "extra": []})
        in_(f"mac dinh: {m['ten']} {w}x{h}")


def cai_long_tieng():
    lock, sc = LT / "long_tieng_lock.txt", LT / "long_tieng.py"
    if not (lock.is_file() and sc.is_file()):
        raise SystemExit(f"thieu {sc} hoac {lock}: chep thu muc long_tieng tu bo cai vao {LT}")
    py = py_env(LT / "env")
    if py and "ok" in _chay([str(py), "-c", "import vieneu; print('ok')"], 120):
        in_(f"da co  moi truong long tieng: {py}")
        return
    uv = shutil.which("uv")
    if uv:
        in_("dung uv: tao moi truong Python 3.11 va cai dung phien ban da thu")
        subprocess.run([uv, "venv", str(LT / "env"), "--python", "3.11"], check=True)
        py = py_env(LT / "env")
        subprocess.run([uv, "pip", "install", "--python", str(py), "-r", str(lock)], check=True)
    else:
        in_(f"khong co uv: dung venv + pip cua Python {sys.version.split()[0]} (ban da thu la 3.11)")
        subprocess.run([sys.executable, "-m", "venv", str(LT / "env")], check=True)
        py = py_env(LT / "env")
        subprocess.run([str(py), "-m", "pip", "install", "--no-cache-dir", "-r", str(lock)], check=True)
    if "ok" not in _chay([str(py), "-c", "import vieneu; print('ok')"], 300):
        raise SystemExit("cai xong nhung khong nap duoc vieneu")
    in_("xong  long tieng (mo hinh 0,76 GB tu tai o lan long tieng dau tien)")


# ---------- tự chạy khi mở máy ----------

def _lenh_chay():
    py = Path(sys.executable)
    if WIN and (py.parent / "pythonw.exe").is_file():
        py = py.parent / "pythonw.exe"  # không hiện cửa sổ đen
    return [str(py), "-I", str(APP / "xuong_phim.py"), "--khong-mo"]


def tu_khoi_dong(bat):
    lenh = _lenh_chay()
    if WIN:
        thu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        lnk = thu / "Xuong phim.lnk"
        if not bat:
            lnk.unlink(missing_ok=True)
            in_(f"da tat tu khoi dong ({lnk})")
            return
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:XP_LNK);"
              "$s.TargetPath=$env:XP_PY;$s.Arguments=$env:XP_ARGS;$s.WorkingDirectory=$env:XP_DIR;"
              "$s.WindowStyle=7;$s.Save()")
        env = dict(os.environ, XP_LNK=str(lnk), XP_PY=lenh[0], XP_DIR=str(APP),
                   XP_ARGS=" ".join(f'"{x}"' if " " in x else x for x in lenh[1:]))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True,
                       creationflags=0x08000000)
        in_(f"da bat tu khoi dong: {lnk}")
    elif MAC:
        pl = Path.home() / "Library" / "LaunchAgents" / "vn.xuongphim.plist"
        if not bat:
            _chay(["launchctl", "unload", str(pl)])
            pl.unlink(missing_ok=True)
            in_("da tat tu khoi dong")
            return
        pl.parent.mkdir(parents=True, exist_ok=True)
        args = "".join(f"<string>{x}</string>" for x in lenh)
        pl.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                      f'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
                      f'<key>Label</key><string>vn.xuongphim</string><key>ProgramArguments</key><array>{args}</array>'
                      f'<key>WorkingDirectory</key><string>{APP}</string><key>RunAtLoad</key><true/></dict></plist>\n')
        _chay(["launchctl", "load", "-w", str(pl)])
        in_(f"da bat tu khoi dong: {pl}")
    else:
        dv = Path.home() / ".config" / "systemd" / "user" / "xuong-phim.service"
        if not bat:
            _chay(["systemctl", "--user", "disable", "--now", "xuong-phim.service"])
            dv.unlink(missing_ok=True)
            in_("da tat tu khoi dong")
            return
        dv.parent.mkdir(parents=True, exist_ok=True)
        dv.write_text("[Unit]\nDescription=Xuong phim\n\n[Service]\nExecStart=" + " ".join(f'"{x}"' for x in lenh) +
                      f"\nWorkingDirectory={APP}\nRestart=on-failure\n\n[Install]\nWantedBy=default.target\n")
        out = _chay(["systemctl", "--user", "enable", "--now", "xuong-phim.service"])
        in_(f"da bat tu khoi dong: {dv}\n{out}".strip())


def trang_thai_tu_khoi_dong():
    if WIN:
        return (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
                / "Xuong phim.lnk").is_file()
    if MAC:
        return (Path.home() / "Library" / "LaunchAgents" / "vn.xuongphim.plist").is_file()
    return (Path.home() / ".config" / "systemd" / "user" / "xuong-phim.service").is_file()


# ---------- kiểm tra ----------

def kiem():
    ok = True
    p = sd_cli_path()
    in_(f"{'OK ' if p.is_file() else '-- '} sd-cli {p}")
    for m in DM["video"]:
        da = mo_hinh_da_cai(m)
        in_(f"{'OK ' if da else '-- '} {m['id']:<12} {m['ten']}" + ("" if da else f" (can tai {can_tai(m) / 2 ** 30:.1f} GB)"))
    py = py_env(LT / "env")
    in_(f"{'OK ' if py else '-- '} long tieng {py or LT / 'env'}")
    in_(f"{'OK ' if shutil.which('ffmpeg') else '-- '} ffmpeg")
    in_(f"cau hinh: {doc_cau_hinh().get('video')}")
    return ok


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="lenh", required=True)
    k = sp.add_parser("kiem_may")
    k.add_argument("--json", action="store_true")
    sp.add_parser("de_xuat")
    s = sp.add_parser("sd_cli")
    s.add_argument("--ban")
    m = sp.add_parser("mo_hinh")
    m.add_argument("ids", nargs="+")
    m.add_argument("--mac_dinh", action="store_true")
    m.add_argument("--w", type=int)
    m.add_argument("--h", type=int)
    sp.add_parser("long_tieng")
    t = sp.add_parser("tu_khoi_dong")
    t.add_argument("che_do", choices=["bat", "tat"])
    sp.add_parser("kiem")
    a = ap.parse_args()

    if a.lenh == "kiem_may":
        d = de_xuat()
        if a.json:
            in_(json.dumps(d, ensure_ascii=False, indent=1))
            return
        may = d["may"]
        in_(f"May: {may['cpu']}, {may['nhan']} luong, RAM {may['ram_gb']} GB, o dia trong {may['o_dia_trong_gb']} GB")
        for g in may["gpu"]:
            in_(f"GPU: {g['ten']} " + ("(dung chung RAM)" if g["uma"] else f"({g['vram_gb']:.0f} GB rieng)"))
        in_(f"Ngan sach bo nho cho video: {d['ngan_sach_gb']} GB ({d['ngan_sach_mo_ta']})")
        v = d["video"]
        in_(f"De xuat video: {v['ten']} {v['w']}x{v['h']} {' '.join(v['extra'])}" if v else "De xuat video: khong co")
        for c in d["canh_bao"]:
            in_(f"Canh bao: {c}")
    elif a.lenh == "de_xuat":
        d = de_xuat()
        v = d["video"]
        in_(f"de xuat: {v['ten'] if v else 'khong co video'}; sd-cli {d['sd_cli_ban']}")
        for c in d["canh_bao"]:
            in_(f"canh bao: {c}")
        if v:
            cai_sd_cli(d["sd_cli_ban"])
            cai_mo_hinh([v["id"]])
            luu_cau_hinh(video={"id": v["id"], "w": v["w"], "h": v["h"], "extra": v["extra"]},
                         may={"cpu": d["may"]["cpu"], "ram_gb": d["may"]["ram_gb"],
                              "gpu": [g["ten"] for g in d["may"]["gpu"]]})
            in_(f"mac dinh: {v['ten']} {v['w']}x{v['h']}")
        cai_long_tieng()
    elif a.lenh == "sd_cli":
        cai_sd_cli(a.ban)
    elif a.lenh == "mo_hinh":
        cai_mo_hinh(a.ids, a.mac_dinh, a.w, a.h)
    elif a.lenh == "long_tieng":
        cai_long_tieng()
    elif a.lenh == "tu_khoi_dong":
        tu_khoi_dong(a.che_do == "bat")
    elif a.lenh == "kiem":
        kiem()


if __name__ == "__main__":
    main()
