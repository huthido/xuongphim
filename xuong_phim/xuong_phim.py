"""Xưởng phim: giao diện trên trình duyệt cho bộ công cụ làm phim (tạo ảnh, tạo video, lồng tiếng, ghép phim).
Chỉ cần Python 3.9+ (thư viện chuẩn); chạy trên Windows, Linux, macOS. Xem HUONG_DAN_XUONG_PHIM.md.

  python xuong_phim.py [--cong 8765] [--khong-mo]

Chỉ nghe ở 127.0.0.1 (máy này). Mỗi lần chạy một việc, các việc khác xếp hàng (máy 16 GB rất sát RAM).
Giao diện (thư mục web/) mở ở http://127.0.0.1:8765/, hoặc từ một tên miền HTTPS (vd triển khai trên Coolify) mà người
dùng đã bấm cho phép trên máy này: trang đó gọi thẳng về 127.0.0.1, mọi việc vẫn chạy trên máy này.
Thư mục công cụ (tao_video, tao_video_amd, long_tieng, tao_anh.py ...) nằm cạnh thư mục xuong_phim,
hoặc đặt biến môi trường XUONG_PHIM_GOC.
"""
import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # chạy với -I thì thư mục script không có trong path
import cai_dat as cd  # noqa: E402  (cùng thư mục: kiểm tra máy, danh mục mô hình, cài đặt)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

APP = Path(__file__).resolve().parent
WEB = APP / "web"
NGUON_CHO_PHEP = APP / "nguon_cho_phep.json"   # các trang (origin) được người dùng cho phép điều khiển máy này
PHIEN_BAN = "1.1.0"
GOC = Path(os.environ.get("XUONG_PHIM_GOC") or APP.parent).resolve()
SP = APP / "san_pham"          # sản phẩm: ảnh, video, tiếng, phim, file tải lên
VIEC = APP / "viec"            # mỗi việc một thư mục: viec.json, log.txt, đầu vào
TT_MAY_CHU = APP / ".may_chu.json"   # cổng đang dùng, để mcp_xuong_phim.py và lần mở sau tìm thấy
LOAI_TEP = {"anh": "Ảnh", "video": "Video", "tieng": "Tiếng", "phim": "Phim", "tai_len": "Tải lên"}
DUOI = {"anh": {".png", ".jpg", ".jpeg", ".webp"}, "video": {".mp4", ".webm", ".mov", ".mkv"},
        "tieng": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}}
WIN = sys.platform == "win32"
TOKEN = secrets.token_urlsafe(24)
KHOA = threading.Lock()
CO_VIEC = threading.Event()
DS_VIEC = {}                   # id -> dict
DANG_CHAY = {}                 # id -> Popen
CONG = {"so": None}            # cổng đang nghe
TINH = {"/": ("index.html", "text/html; charset=utf-8"),       # tệp tĩnh của giao diện và PWA
        "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
        "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
        "/ngoai_tuyen.html": ("ngoai_tuyen.html", "text/html; charset=utf-8"),
        "/icon.svg": ("icon.svg", "image/svg+xml"),
        "/icon-192.png": ("icon-192.png", "image/png"),
        "/icon-512.png": ("icon-512.png", "image/png"),
        "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png")}
HUONG_DAN = {                  # tên -> các chỗ có thể có tệp hướng dẫn (lấy chỗ đầu tiên tồn tại)
    "xuong_phim": ["HUONG_DAN_XUONG_PHIM.md"],
    "video_sd": ["tao_video_amd/HUONG_DAN_CAI_TAO_VIDEO_AMD.md"],
    "video_intel": ["tao_video/HUONG_DAN_CAI_TAO_VIDEO.md"],
    "tong": ["HUONG_DAN_CAI_LAM_PHIM.md", "bo_cai_lam_phim/HUONG_DAN_CAI_LAM_PHIM.md"],
}


# ---------- công cụ ----------

def py_env(thu_muc):
    p = thu_muc / ("Scripts/python.exe" if WIN else "bin/python")
    return p if p.is_file() else None


def tim_ffmpeg():
    p = shutil.which("ffmpeg")
    if not p and WIN:
        goc = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        p = next((str(x) for x in goc.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe")), None)
    return p


def cong_cu():
    """Kiểm tra công cụ nào đã cài. Mỗi mục: {co: bool, ly_do: str}."""
    k = {}
    ff = tim_ffmpeg()
    k["ffmpeg"] = {"co": bool(ff), "ly_do": "" if ff else "chưa cài ffmpeg"}

    py = py_env(GOC / "fastsdcpu" / "env")
    ok = py and (GOC / "tao_anh.py").is_file()
    k["anh"] = {"co": bool(ok), "ly_do": "" if ok else "chưa cài tao_anh.py (FLUX.2 klein, OpenVINO)"}

    sd_ok = (GOC / "tao_video_amd" / "tao_video_sd.py").is_file() and cd.sd_cli_path().is_file()
    da_cai = [m for m in cd.DM["video"] if cd.mo_hinh_da_cai(m)] if sd_ok else []
    w22 = any(m["ho"] == "wan22" for m in da_cai)
    w21 = any(m["ho"] == "wan21" for m in da_cai)
    k["wan22"] = {"co": bool(w22), "ly_do": "" if w22 else "chưa cài sd-cli hoặc mô hình Wan2.2 5B trong tao_video_amd"}
    k["wan21_sd"] = {"co": bool(w21), "ly_do": "" if w21 else "chưa cài sd-cli hoặc mô hình Wan2.1 trong tao_video_amd"}

    ov = py_env(GOC / "tao_video" / "env") and (GOC / "tao_video" / "tao_video.py").is_file()
    k["wan21_ov"] = {"co": bool(ov), "ly_do": "" if ov else "chưa cài tao_video (OpenVINO, Intel)"}

    lt = py_env(GOC / "long_tieng" / "env") and (GOC / "long_tieng" / "long_tieng.py").is_file()
    k["tieng"] = {"co": bool(lt), "ly_do": "" if lt else "chưa cài long_tieng (VieNeu)"}
    for ten in ("anh", "wan22", "wan21_sd", "wan21_ov", "tieng"):
        if k[ten]["co"] and not ff:
            k[ten] = {"co": False, "ly_do": "chưa cài ffmpeg"}
    k["ghep"] = k["ffmpeg"]
    k["mo_hinh_video"] = [{"id": m["id"], "ten": m["ten"], "ho": m["ho"], "da_thu": m["da_thu"]} for m in da_cai]
    return k


def tep_huong_dan(ten):
    for r in HUONG_DAN.get(ten, []):
        for goc in (APP, GOC):
            p = goc / r
            if p.is_file():
                return p
    return None


def thiet_lap():
    """Thông tin cho thẻ Thiết lập: máy, đường dẫn thật, lệnh gắn MCP, tình trạng công cụ."""
    py, mcp = sys.executable, str(APP / "mcp_xuong_phim.py")
    sd = Path(os.environ.get("SD_CLI") or GOC / "tao_video_amd" / "sd" / ("sd-cli.exe" if WIN else "sd-cli"))
    lt = py_env(GOC / "long_tieng" / "env")
    return {
        "he_dieu_hanh": sys.platform, "may": f"{sys.platform} {os.environ.get('PROCESSOR_ARCHITECTURE', '')}".strip(),
        "python": py, "python_ban": sys.version.split()[0], "app": str(APP), "goc": str(GOC), "cong": CONG["so"],
        "ffmpeg": tim_ffmpeg(), "sd_cli": str(sd) if sd.is_file() else None,
        "co_tep": {"tao_video_sd": (GOC / "tao_video_amd" / "tao_video_sd.py").is_file(),
                   "long_tieng_py": (GOC / "long_tieng" / "long_tieng.py").is_file(),
                   "long_tieng_lock": (GOC / "long_tieng" / "long_tieng_lock.txt").is_file(),
                   "long_tieng_env": bool(lt)},
        "mcp": {"claude": f'claude mcp add xuong-phim -- "{py}" -I "{mcp}"',
                "json": {"mcpServers": {"xuong-phim": {"command": py, "args": ["-I", mcp]}}}},
        "huong_dan": {k: bool(tep_huong_dan(k)) for k in HUONG_DAN},
        "cong_cu": cong_cu(),
        "tu_khoi_dong": cd.trang_thai_tu_khoi_dong(),
        "nguon_cho_phep": doc_nguon(),
        "phien_ban": PHIEN_BAN,
    }


def danh_muc():
    """Danh mục mô hình kèm đã cài chưa, cần tải bao nhiêu, và cấu hình mặc định."""
    return {"video": [dict(m, da_cai=cd.mo_hinh_da_cai(m), can_tai_gb=round(cd.can_tai(m) / 2 ** 30, 1))
                      for m in cd.DM["video"]],
            "kich_thuoc": cd.DM["kich_thuoc"], "cau_hinh": cd.doc_cau_hinh()}


def doc_nguon():
    try:
        return [x for x in json.loads(NGUON_CHO_PHEP.read_text(encoding="utf-8")) if isinstance(x, str)]
    except (OSError, ValueError):
        return []


def nguon_hop_le(o):
    """https://ten-mien[:cổng], hoặc http://localhost / 127.0.0.1 khi thử trên máy."""
    return bool(re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d{1,5})?", o or "")
                or re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d{1,5})?", o or ""))


def ram():
    """(còn trống, tổng) tính bằng GB, hoặc None nếu không đọc được."""
    try:
        if WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tong", ctypes.c_ulonglong),
                            ("con", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                            ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
            s = MS()
            s.len = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.con / 2 ** 30, s.tong / 2 ** 30
        if sys.platform.startswith("linux"):
            d = {}
            for dong in Path("/proc/meminfo").read_text().splitlines():
                ten, gt = dong.split(":", 1)
                d[ten] = int(gt.split()[0])
            return d["MemAvailable"] / 2 ** 20, d["MemTotal"] / 2 ** 20
        if sys.platform == "darwin":
            tong = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
            vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
            trang = int(re.search(r"page size of (\d+)", vm).group(1))
            so = sum(int(re.search(rf"{t}:\s+(\d+)", vm).group(1)) for t in ("Pages free", "Pages inactive"))
            return so * trang / 2 ** 30, tong / 2 ** 30
    except Exception:
        pass
    return None


# ---------- tệp ----------

def ten_an_toan(s, dai=40):
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._")
    return s[:dai] or "tep"


def tep_trong(loai, ten):
    """Đường dẫn tệp trong thư viện, chặn đi ra ngoài thư mục."""
    if loai not in LOAI_TEP or not ten or "/" in ten or "\\" in ten or ten.startswith("."):
        raise ValueError("tệp không hợp lệ")
    p = (SP / loai / ten).resolve()
    if p.parent != (SP / loai).resolve():
        raise ValueError("tệp không hợp lệ")
    return p


def tham_chieu(ref, can_co=True):
    """'loai/ten' -> Path."""
    if not ref:
        return None
    loai, _, ten = str(ref).partition("/")
    p = tep_trong(loai, ten)
    if can_co and not p.is_file():
        raise ValueError(f"không thấy tệp {ref}")
    return p


def kieu_tep(p):
    d = p.suffix.lower()
    for k, s in DUOI.items():
        if d in s:
            return k
    return "khac"


def ds_tep():
    ra = []
    for loai in LOAI_TEP:
        for p in (SP / loai).glob("*"):
            if p.is_file() and not p.name.startswith(".") and ".tmp." not in p.name:
                st = p.stat()
                ra.append({"ref": f"{loai}/{p.name}", "loai": loai, "ten": p.name, "kieu": kieu_tep(p),
                           "co": st.st_size, "luc": st.st_mtime})
    ra.sort(key=lambda x: -x["luc"])
    return ra


# ---------- việc ----------

def luu(v):
    (VIEC / v["id"] / "viec.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")


def nhan(prefix, chu):
    return f"{time.strftime('%m%d_%H%M%S')}_{ten_an_toan(chu, 28)}" if chu else f"{time.strftime('%m%d_%H%M%S')}_{prefix}"


def so(x, mac_dinh, nho, lon):
    try:
        x = int(float(x))
    except (TypeError, ValueError):
        return mac_dinh
    return max(nho, min(lon, x))


def tao_viec(d):
    """Dựng lệnh cho một việc từ dữ liệu giao diện gửi lên. Trả về dict việc (chưa xếp hàng)."""
    loai = d.get("loai")
    k = cong_cu()
    vid = f"{time.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"
    thu = VIEC / vid
    thu.mkdir(parents=True)
    vao = thu / "vao.json"
    ra, tieu_de = [], ""

    if loai == "anh":
        if not k["anh"]["co"]:
            raise ValueError(k["anh"]["ly_do"])
        p = (d.get("prompt") or "").strip()
        if not p:
            raise ValueError("chưa có lời mô tả")
        n = so(d.get("so_anh"), 1, 1, 8)
        seed = so(d.get("seed"), 7, 0, 2 ** 31 - 1)
        w, h = so(d.get("w"), 1248, 256, 2048), so(d.get("h"), 720, 256, 2048)
        ref = tham_chieu(d.get("ref"))
        ten = nhan("anh", p)
        jobs = []
        for i in range(n):
            out = SP / "anh" / (f"{ten}_s{seed + i}.png")
            j = {"prompt": p, "out": str(out), "w": w, "h": h, "seed": seed + i}
            if ref:
                j["ref"] = [str(ref)]
            jobs.append(j)
            ra.append(out)
        cmd = [str(py_env(GOC / "fastsdcpu" / "env")), "-I", str(GOC / "tao_anh.py"), "--jobs", str(vao)]
        tieu_de = f"Ảnh: {p[:60]}"

    elif loai == "video":
        mh = d.get("mo_hinh") or "wan22"
        ids = {m["id"] for m in cd.DM["video"]}
        if mh not in ("wan22", "wan21_sd", "wan21_ov") and mh not in ids:
            raise ValueError("mô hình không hợp lệ")
        mo = chon_mo_hinh(mh)
        if mo is None:
            if not k["wan21_ov"]["co"]:
                raise ValueError(k["wan21_ov"]["ly_do"])
        elif not (k["ffmpeg"]["co"] and cd.sd_cli_path().is_file() and cd.mo_hinh_da_cai(mo)):
            raise ValueError(f"chưa cài {mo['ten']}: vào thẻ Thiết lập để tải")
        p = (d.get("prompt") or "").strip()
        if not p:
            raise ValueError("chưa có lời mô tả")
        anh = tham_chieu(d.get("anh"))
        if anh and not (mo and mo["ho"] == "wan22"):
            raise ValueError("chỉ Wan2.2 5B nhận ảnh khung đầu")
        w, h = so(d.get("w"), 640, 128, 1280), so(d.get("h"), 352, 128, 1280)
        fr = so(d.get("frames"), 121, 5, 241)
        seed = so(d.get("seed"), 7, 0, 2 ** 31 - 1)
        out = SP / "video" / f"{nhan('video', p)}.mp4"
        jobs = [{"prompt": p, "out": str(out), "w": w, "h": h, "frames": fr, "seed": seed}]
        if anh:
            jobs[0]["anh"] = str(anh)
        if mo is None:
            cmd = [str(py_env(GOC / "tao_video" / "env")), "-I", str(GOC / "tao_video" / "tao_video.py"),
                   "--jobs", str(vao)]
        else:
            tep = lambda k: str(cd.MODELS / cd.DM["tep"][mo[k]]["duong_dan"])  # noqa: E731
            cmd = [sys.executable, "-I", str(GOC / "tao_video_amd" / "tao_video_sd.py"), "--mo-hinh", mo["ho"],
                   "--diffusion", tep("diffusion"), "--t5", tep("t5"), "--tae", tep("tae"), "--jobs", str(vao)]
            extra = [x for x in (d.get("extra") or (cd.doc_cau_hinh().get("video") or {}).get("extra") or [])
                     if x in ("--offload-to-cpu",)]
            if extra:
                cmd += ["--extra", " ".join(extra)]
            if d.get("cpu"):
                cmd.append("--cpu")
            d["mo_hinh"] = mo["id"]
        ra.append(out)
        tieu_de = f"Video {w}x{h} {fr} khung" + (f" ({mo['ten']})" if mo else "") + f": {p[:60]}"

    elif loai == "tieng":
        if not k["tieng"]["co"]:
            raise ValueError(k["tieng"]["ly_do"])
        jobs = []
        goc_ten = time.strftime("%m%d_%H%M%S")
        for i, dong in enumerate(d.get("dong") or [], 1):
            cau = (dong.get("cau") or "").strip()
            if not cau:
                continue
            ten = f"{goc_ten}_{i:02d}_{ten_an_toan(dong.get('giong') or 'mac_dinh', 16)}"
            jobs.append({"ten": ten, "giong": dong.get("giong") or "", "cau": cau,
                         "cao_do": max(-12.0, min(12.0, float(dong.get("cao_do") or 0)))})
            ra.append(SP / "tieng" / f"{ten}.mp3")
        if not jobs:
            raise ValueError("chưa có câu nào")
        cmd = [str(py_env(GOC / "long_tieng" / "env")), "-I", str(GOC / "long_tieng" / "long_tieng.py"),
               "--loi", str(vao), "--out", str(SP / "tieng")]
        tieu_de = f"Lồng tiếng {len(jobs)} câu: {jobs[0]['cau'][:50]}"

    elif loai == "ghep":
        if not k["ghep"]["co"]:
            raise ValueError(k["ghep"]["ly_do"])
        canh = []
        for c in d.get("canh") or []:
            if not c.get("video"):
                continue
            if kieu_tep(tham_chieu(c["video"])) != "video":
                raise ValueError(f"{c['video']} không phải video")
            if c.get("tieng") and kieu_tep(tham_chieu(c["tieng"])) != "tieng":
                raise ValueError(f"{c['tieng']} không phải tệp âm thanh")
            canh.append({"video": str(tham_chieu(c["video"])),
                         "tieng": str(tham_chieu(c["tieng"])) if c.get("tieng") else None,
                         "tre": max(0.0, min(30.0, float(c.get("tre") or 0))),
                         "bo_dau": max(0.0, min(30.0, float(c.get("bo_dau") or 0)))})
        if not canh:
            raise ValueError("chưa có cảnh nào")
        ten = ten_an_toan(d.get("ten") or "", 40) if d.get("ten") else nhan("phim", "")
        out = SP / "phim" / f"{ten}.mp4"
        if out.exists():
            out = SP / "phim" / f"{ten}_{time.strftime('%H%M%S')}.mp4"
        jobs = {"out": str(out), "w": so(d.get("w"), 1280, 128, 3840), "h": so(d.get("h"), 720, 128, 2160),
                "fps": so(d.get("fps"), 24, 8, 60), "canh": canh,
                "nhac": str(tham_chieu(d["nhac"])) if d.get("nhac") else None,
                "am_luong_nhac": max(0.0, min(1.0, float(d.get("am_luong_nhac") or 0.15)))}
        cmd = [sys.executable, "-I", str(APP / "ghep_phim.py"), "--jobs", str(vao)]
        ra.append(out)
        tieu_de = f"Ghép phim {len(canh)} cảnh → {out.name}"

    elif loai == "cai":
        lenh, ts = d.get("lenh"), [str(x) for x in (d.get("tham_so") or [])]
        hop_le = {"de_xuat": [], "sd_cli": ["--ban", "vulkan", "cpu", "cuda", "rocm", "metal"],
                  "mo_hinh": [m["id"] for m in cd.DM["video"]] + ["--mac_dinh", "--w", "--h"],
                  "long_tieng": [], "tu_khoi_dong": ["bat", "tat"]}
        if lenh not in hop_le or any(x not in hop_le[lenh] and not x.isdigit() for x in ts):
            raise ValueError("lệnh cài không hợp lệ")
        jobs = None
        cmd = [sys.executable, "-I", str(APP / "cai_dat.py"), lenh, *ts]
        tieu_de = {"de_xuat": "Cài theo đề xuất cho máy này", "sd_cli": "Cài sd-cli", "long_tieng": "Cài lồng tiếng VieNeu",
                   "tu_khoi_dong": "Bật tự chạy khi mở máy" if "bat" in ts else "Tắt tự chạy khi mở máy"}.get(
            lenh, "Tải mô hình " + " ".join(x for x in ts if not x.startswith("-") and not x.isdigit()))

    elif loai == "giong":
        if not k["tieng"]["co"]:
            raise ValueError(k["tieng"]["ly_do"])
        jobs = None
        cmd = [str(py_env(GOC / "long_tieng" / "env")), "-I", str(GOC / "long_tieng" / "long_tieng.py"), "--giong"]
        tieu_de = "Cập nhật danh sách giọng"
    else:
        raise ValueError("loại việc không hợp lệ")

    if jobs is not None:
        vao.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": vid, "loai": loai, "tieu_de": tieu_de, "lenh": cmd, "ra": [str(x) for x in ra],
            "trang_thai": "cho", "tao_luc": time.time(), "bat_dau": None, "ket_thuc": None, "ma": None,
            "dau_vao": d}


def xep_hang(v):
    with KHOA:
        DS_VIEC[v["id"]] = v
        luu(v)
    CO_VIEC.set()


def giu_may_thuc(bat):
    if WIN:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if bat else 0))
        return None
    if not bat:
        return None
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        return subprocess.Popen(["caffeinate", "-i"])
    if shutil.which("systemd-inhibit"):
        return subprocess.Popen(["systemd-inhibit", "--what=idle:sleep", "--who=xuong_phim", "--why=dang chay viec",
                                 "--mode=block", "sleep", "infinity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def doc_giong(log):
    ds = []
    for dong in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if " | " in dong:
            ma, mo_ta = dong.split(" | ", 1)
            ds.append({"ma": ma.strip(), "mo_ta": mo_ta.strip().lstrip("⭐ ").strip()})
    if ds:
        (APP / "giong.json").write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")


def ram_can(v):
    """RAM trống (GB) cần có trước khi bắt đầu việc.
    Video Wan2.2 640x352: đo 16/10/2026 bắt đầu với 6,2 GB trống thì chạy được (mô hình 7,2 GB trên GPU dùng chung,
    Windows tự dồn bớt bộ nhớ ứng dụng khác); 832x480x121 xin khoảng 19 GB. Các số còn lại là ước lượng, chưa đo."""
    d = v.get("dau_vao") or {}
    if v["loai"] == "video":
        w, h = so(d.get("w"), 640, 128, 1280), so(d.get("h"), 352, 128, 1280)
        m = chon_mo_hinh(d.get("mo_hinh"))
        if not m:  # OpenVINO
            return 6.0
        can = m["bo_nho_gb"] + cd.bo_nho_lam_viec(m["ho"], w, h)
        may = may_cache()
        if any(not g["uma"] for g in may["gpu"]):  # GPU rời: RAM chỉ giữ chương trình (cộng trọng số nếu offload)
            return 4.0 + (m["bo_nho_gb"] if "--offload-to-cpu" in (d.get("extra") or []) else 0)
        # GPU dùng chung RAM: hệ điều hành đẩy bớt ứng dụng khác ra bộ nhớ ảo được khoảng 8 GB (máy gốc: Q4 640x352
        # cần 14,1 GB, bắt đầu với 6,2 GB trống vẫn chạy được)
        return round(max(6.0, can - 8.1), 1)
    return {"anh": 4.0, "tieng": 1.5, "giong": 1.5, "ghep": 0.5, "cai": 0.3}.get(v["loai"], 1.0)


_MAY = {"luc": 0, "may": None}


def may_cache(lam_moi=False):
    """Cấu hình máy (cai_dat.kiem_may) lưu đệm 10 phút: chạy sd-cli --list-devices mất vài giây."""
    if lam_moi or not _MAY["may"] or time.time() - _MAY["luc"] > 600:
        _MAY.update(luc=time.time(), may=cd.kiem_may())
    return _MAY["may"]


def chon_mo_hinh(mh):
    """Mục trong mo_hinh.json ứng với lựa chọn của giao diện; None nghĩa là bản OpenVINO."""
    if mh == "wan21_ov":
        return None
    ds = {m["id"]: m for m in cd.DM["video"]}
    if mh in ds:
        return ds[mh]
    ho = "wan21" if mh == "wan21_sd" else "wan22"   # tên cũ: wan22 / wan21_sd
    mac_dinh = (cd.doc_cau_hinh().get("video") or {}).get("id")
    if mac_dinh in ds and ds[mac_dinh]["ho"] == ho and cd.mo_hinh_da_cai(ds[mac_dinh]):
        return ds[mac_dinh]
    return next((m for m in sorted(cd.DM["video"], key=lambda m: -m["chat_luong"])
                 if m["ho"] == ho and cd.mo_hinh_da_cai(m)), ds["wan22_5b_q4" if ho == "wan22" else "wan21_13b"])


_AN_RAM = {"luc": 0, "ds": []}


def ung_dung_an_ram(n=6):
    """Các ứng dụng đang chiếm nhiều RAM nhất (gộp theo tên), để gợi ý người dùng đóng bớt. Lưu đệm 10 giây."""
    if time.time() - _AN_RAM["luc"] < 10:
        return _AN_RAM["ds"]
    tong = {}
    try:
        if WIN:
            out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW).stdout
            for dong in out.splitlines():
                cot = [c.strip('"') for c in dong.split('","')]
                if len(cot) >= 5:
                    tong[cot[0]] = tong.get(cot[0], 0) + int(re.sub(r"\D", "", cot[4]) or 0) / 2 ** 20
        elif sys.platform.startswith("linux"):
            for p in Path("/proc").glob("[0-9]*/status"):
                try:
                    t = p.read_text()
                except OSError:
                    continue
                ten = re.search(r"Name:\s+(.+)", t)
                rss = re.search(r"VmRSS:\s+(\d+)", t)
                if ten and rss:
                    tong[ten.group(1)] = tong.get(ten.group(1), 0) + int(rss.group(1)) / 2 ** 20
        else:
            out = subprocess.run(["ps", "-axo", "rss=,comm="], capture_output=True, text=True).stdout
            for dong in out.splitlines():
                rss, _, ten = dong.strip().partition(" ")
                if rss.isdigit():
                    ten = Path(ten.strip()).name
                    tong[ten] = tong.get(ten, 0) + int(rss) / 2 ** 20
    except Exception:
        pass
    bo = {"System", "Registry", "Memory Compression", "MsMpEng.exe", "svchost.exe", "dwm.exe", "explorer.exe",
          "csrss.exe", "kernel_task", "WindowServer", "systemd", "Xorg"}
    ds = sorted(((t, g) for t, g in tong.items() if t not in bo and g >= 0.2), key=lambda x: -x[1])[:n]
    _AN_RAM.update(luc=time.time(), ds=[{"ten": t, "gb": round(g, 1)} for t, g in ds])
    return _AN_RAM["ds"]


def tho_lam():
    """Luồng chạy việc: lấy việc chờ lâu nhất, chạy xong mới lấy việc kế."""
    while True:
        CO_VIEC.wait()
        with KHOA:
            cho = sorted((v for v in DS_VIEC.values() if v["trang_thai"] == "cho"), key=lambda v: v["tao_luc"])
            if not cho:
                CO_VIEC.clear()
                continue
            v = cho[0]
        # Mỗi việc là một tiến trình riêng, xong thì thoát hẳn nên RAM/bộ nhớ GPU của bước trước đã được trả.
        # Còn lại là các ứng dụng khác của máy: chưa đủ RAM trống thì chờ, chỉ cho người dùng ứng dụng nào đang chiếm.
        can, r = ram_can(v), ram()
        if r and r[0] < can and not v.get("bo_qua_ram"):
            with KHOA:
                if v["trang_thai"] == "cho":
                    v["cho_ram"] = {"can": can, "con": round(r[0], 1)}
                    luu(v)
            time.sleep(5)
            continue
        with KHOA:
            if v["trang_thai"] != "cho":  # bị huỷ trong lúc chờ RAM
                continue
            v.pop("cho_ram", None)
            v["trang_thai"], v["bat_dau"] = "dang_chay", time.time()
            luu(v)
        thu = VIEC / v["id"]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", HF_HUB_DISABLE_PROGRESS_BARS="1")
        ff = tim_ffmpeg()
        if ff:  # long_tieng.py gọi ffmpeg/ffprobe theo tên; winget không tự thêm PATH cho cửa sổ đang mở
            env["PATH"] = str(Path(ff).parent) + os.pathsep + env.get("PATH", "")
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if WIN \
            else {"start_new_session": True}
        phu = giu_may_thuc(True)
        try:
            with open(thu / "log.txt", "wb") as log:
                pr = subprocess.Popen(v["lenh"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      cwd=str(thu), env=env, **kw)
                with KHOA:
                    DANG_CHAY[v["id"]] = pr
                    v["pid"] = pr.pid
                    luu(v)
                ma = pr.wait()
        except Exception as e:
            ma = -1
            with open(thu / "log.txt", "a", encoding="utf-8") as log:
                log.write(f"\nkhong chay duoc: {e}\n")
        finally:
            giu_may_thuc(False)
            if phu:
                phu.terminate()
        with KHOA:
            DANG_CHAY.pop(v["id"], None)
            v["ket_thuc"], v["ma"] = time.time(), ma
            if v["trang_thai"] != "da_huy":
                v["trang_thai"] = "xong" if ma == 0 and all(Path(p).exists() for p in v["ra"]) else "loi"
            if v["loai"] == "giong" and ma == 0:
                doc_giong(thu / "log.txt")
            if v["loai"] == "cai":
                _MAY["luc"] = 0  # cài xong thì đọc lại máy / sd-cli
            luu(v)


def huy(vid):
    with KHOA:
        v = DS_VIEC.get(vid)
        if not v or v["trang_thai"] not in ("cho", "dang_chay"):
            return False
        v["trang_thai"] = "da_huy"
        if v["id"] not in DANG_CHAY:
            v["ket_thuc"] = time.time()
        luu(v)
        pr = DANG_CHAY.get(vid)
    if pr:  # dừng cả cây tiến trình (sd-cli, ffmpeg chạy dưới script)
        if WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pr.pid)], capture_output=True)
        else:
            try:
                os.killpg(pr.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    return True


def nap_viec_cu():
    """Việc đang chạy/chờ khi ứng dụng tắt: không tự chạy lại, chỉ đánh dấu (có nút Chạy lại)."""
    for f in VIEC.glob("*/viec.json"):
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if v["trang_thai"] in ("cho", "dang_chay"):
            xong = v["trang_thai"] == "dang_chay" and v["ra"] and all(Path(p).exists() for p in v["ra"])
            v["trang_thai"] = "xong" if xong else "bi_ngat"
            luu(v)
        DS_VIEC[v["id"]] = v


def duoi_log(vid, n=6000):
    p = VIEC / vid / "log.txt"
    if not p.is_file():
        return ""
    with open(p, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - n * 4))
        s = f.read().decode("utf-8", errors="replace")
    # thanh tiến trình dùng \r để vẽ lại cùng dòng: chỉ giữ lần vẽ cuối của mỗi dòng
    dong = [x.split("\r")[-1] if x.strip("\r").strip() else "" for x in s.replace("\r\n", "\n").split("\n")]
    s = "\n".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", x) for x in dong if x.strip())
    return s[-n:]


def tom_tat(v):
    x = {k: v.get(k) for k in ("id", "loai", "tieu_de", "trang_thai", "tao_luc", "bat_dau", "ket_thuc", "ma")}
    if v["trang_thai"] == "cho" and v.get("cho_ram") and not v.get("bo_qua_ram"):
        x["cho_ram"] = v["cho_ram"]
    x["ra"] = [f"{Path(p).parent.name}/{Path(p).name}" for p in v["ra"] if Path(p).exists()]
    return x


# ---------- máy chủ ----------

class XuLy(BaseHTTPRequestHandler):
    server_version = "XuongPhim/1"

    def log_message(self, *a):
        pass

    def gui(self, ma, than, kieu="application/json; charset=utf-8", them=None):
        if isinstance(than, (dict, list)):
            than = json.dumps(than, ensure_ascii=False).encode("utf-8")
        elif isinstance(than, str):
            than = than.encode("utf-8")
        self.send_response(ma)
        self.send_header("Content-Type", kieu)
        self.send_header("Content-Length", str(len(than)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if kieu.startswith("text/html"):
            # cấm trang khác nhúng vào khung (iframe): nếu không, trang lạ có thể che trang /cho_phep và dụ người
            # dùng bấm "Cho phép" (clickjacking), tự cho phép mình điều khiển Xưởng phim trên máy
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        for k, gt in (them or {}).items():
            self.send_header(k, gt)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(than)

    def host_dung(self):
        # chặn trang web lạ trỏ tên miền của nó về 127.0.0.1 (DNS rebinding)
        h = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return h in ("127.0.0.1", "localhost", "[::1]")

    def nguon(self):
        """(origin, loại): 'may' = chính trang của máy này hoặc không có Origin; 'cho_phep' = trang đã được cho phép;
        'la' = trang khác."""
        o = self.headers.get("Origin")
        if not o or o in (f"http://127.0.0.1:{CONG['so']}", f"http://localhost:{CONG['so']}"):
            return o, "may"
        return o, "cho_phep" if o in doc_nguon() else "la"

    def end_headers(self):
        o, loai = getattr(self, "_nguon", (None, "may"))
        if o and (loai == "cho_phep" or getattr(self, "_cors_moi", False)):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self):
        # yêu cầu thăm dò của trình duyệt (CORS, Private/Local Network Access) từ trang trên tên miền khác.
        # Trả lời cho mọi trang để trang chưa được phép đọc được lỗi "chưa cho phép"; quyền thật kiểm ở yêu cầu chính.
        o = self.headers.get("Origin")
        if not self.host_dung() or not o:
            return self.gui(403, {"loi": "host"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", o)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        super().end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.host_dung():
            return self.gui(403, {"loi": "host"})
        self._nguon = self.nguon()
        u = urlparse(self.path)
        if u.path == "/api/ket_noi":
            if self._nguon[1] == "la":  # cho trang lạ đọc được lỗi để chỉ người dùng cách cho phép
                self._cors_moi = True
                return self.gui(403, {"loi": "nguon_chua_cho_phep", "nguon": self._nguon[0]})
            return self.gui(200, {"token": TOKEN, "phien_ban": PHIEN_BAN, "cong": CONG["so"]})
        if u.path in TINH:
            ten, kieu = TINH[u.path]
            p = WEB / ten
            if not p.is_file():
                return self.gui(404, {"loi": "không có"})
            return self.gui(200, p.read_bytes(), kieu, {"Cache-Control": "no-cache"})
        if u.path == "/cho_phep":
            return self.gui(200, trang_cho_phep(parse_qs(u.query).get("nguon", [""])[0]), "text/html; charset=utf-8")
        if u.path.startswith("/api/") and self._nguon[1] == "la":
            return self.gui(403, {"loi": "nguon_chua_cho_phep"})
        if u.path == "/api/trang_thai":
            with KHOA:
                ds = sorted(DS_VIEC.values(), key=lambda v: -v["tao_luc"])[:60]
                viec = [tom_tat(v) for v in ds]
            r = ram()
            an_ram = ung_dung_an_ram() if any(x.get("cho_ram") for x in viec) else []
            return self.gui(200, {"cong_cu": cong_cu(), "viec": viec, "bay_gio": time.time(), "an_ram": an_ram,
                                  "thu_muc": str(APP),
                                  "ram": {"con": r[0], "tong": r[1]} if r else None,
                                  "he_dieu_hanh": sys.platform})
        if u.path == "/api/tep":
            return self.gui(200, ds_tep())
        if u.path == "/api/thiet_lap":
            return self.gui(200, dict(thiet_lap(), mo_tu_may=self._nguon[1] == "may"))
        if u.path == "/api/may":
            may = may_cache("moi" in parse_qs(u.query))
            return self.gui(200, cd.de_xuat(may))
        if u.path == "/api/mo_hinh":
            return self.gui(200, danh_muc())
        if u.path == "/api/huong_dan":
            p = tep_huong_dan(parse_qs(u.query).get("ten", [""])[0])
            if not p:
                return self.gui(404, {"loi": "không có tệp hướng dẫn này trên máy"})
            return self.gui(200, {"ten": p.name, "duong_dan": str(p), "noi_dung": p.read_text(encoding="utf-8")})
        if u.path == "/api/giong":
            p = APP / "giong.json"
            return self.gui(200, json.loads(p.read_text(encoding="utf-8")) if p.is_file() else [])
        m = re.fullmatch(r"/api/viec/([\w-]+)", u.path)
        if m:
            with KHOA:
                v = DS_VIEC.get(m.group(1))
            if not v:
                return self.gui(404, {"loi": "không có việc này"})
            return self.gui(200, dict(tom_tat(v), log=duoi_log(v["id"]), dau_vao=v.get("dau_vao")))
        m = re.fullmatch(r"/tep/(\w+)/([^/]+)", u.path)
        if m:
            try:
                p = tep_trong(m.group(1), unquote(m.group(2)))
            except ValueError:
                return self.gui(400, {"loi": "tệp không hợp lệ"})
            if not p.is_file():
                return self.gui(404, {"loi": "không có tệp"})
            return self.gui_tep(p, "tai" in parse_qs(u.query))
        self.gui(404, {"loi": "không có"})

    def gui_tep(self, p, tai_ve):
        co = p.stat().st_size
        kieu = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        dau, cuoi, ma = 0, co - 1, 200
        rg = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if rg and co:  # trình duyệt cần Range để tua video
            if rg.group(1):
                dau = int(rg.group(1))
                cuoi = min(int(rg.group(2)), co - 1) if rg.group(2) else co - 1
            elif rg.group(2):
                dau = max(0, co - int(rg.group(2)))
            if dau > cuoi:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{co}")
                self.end_headers()
                return
            ma = 206
        self.send_response(ma)
        self.send_header("Content-Type", kieu)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(cuoi - dau + 1))
        self.send_header("X-Content-Type-Options", "nosniff")
        if ma == 206:
            self.send_header("Content-Range", f"bytes {dau}-{cuoi}/{co}")
        if tai_ve:
            self.send_header("Content-Disposition", f"attachment; filename=\"{ten_an_toan(p.stem)}{p.suffix}\"")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(p, "rb") as f:
                f.seek(dau)
                con = cuoi - dau + 1
                while con > 0:
                    khuc = f.read(min(1 << 20, con))
                    if not khuc:
                        break
                    self.wfile.write(khuc)
                    con -= len(khuc)
        except (ConnectionError, OSError):
            pass

    def do_POST(self):
        self._nguon = self.nguon()
        if not self.host_dung() or self._nguon[1] == "la" or \
                not hmac.compare_digest(self.headers.get("X-Token") or "", TOKEN):
            return self.gui(403, {"loi": "không được phép"})
        u = urlparse(self.path)
        dai = int(self.headers.get("Content-Length") or 0)
        try:
            if u.path == "/api/tai_len":
                if dai > 2 * 2 ** 30:
                    return self.gui(413, {"loi": "tệp quá lớn (tối đa 2 GB)"})
                goc = unquote(parse_qs(u.query).get("ten", ["tep"])[0])
                duoi = Path(goc).suffix.lower()
                if not any(duoi in s for s in DUOI.values()):
                    return self.gui(400, {"loi": "chỉ nhận ảnh, video, âm thanh"})
                p = SP / "tai_len" / f"{ten_an_toan(Path(goc).stem)}{duoi}"
                i = 1
                while p.exists():
                    p = SP / "tai_len" / f"{ten_an_toan(Path(goc).stem)}_{i}{duoi}"
                    i += 1
                tam = p.with_name(p.name + ".tmp.part")
                with open(tam, "wb") as f:
                    con = dai
                    while con > 0:
                        khuc = self.rfile.read(min(1 << 20, con))
                        if not khuc:
                            break
                        f.write(khuc)
                        con -= len(khuc)
                if con:
                    tam.unlink()
                    return self.gui(400, {"loi": "tải lên bị đứt"})
                tam.replace(p)
                return self.gui(200, {"ref": f"tai_len/{p.name}"})

            d = json.loads(self.rfile.read(dai) or b"{}") if dai else {}
            if u.path == "/api/viec":
                v = tao_viec(d)
                xep_hang(v)
                return self.gui(200, {"id": v["id"]})
            m = re.fullmatch(r"/api/viec/([\w-]+)/(huy|chay_lai|chay_luon)", u.path)
            if m:
                if m.group(2) == "huy":
                    return self.gui(200, {"ok": huy(m.group(1))})
                if m.group(2) == "chay_luon":  # người dùng chấp nhận chạy dù RAM trống chưa đủ
                    with KHOA:
                        v = DS_VIEC.get(m.group(1))
                        if v and v["trang_thai"] == "cho":
                            v["bo_qua_ram"] = True
                            luu(v)
                    return self.gui(200, {"ok": bool(v)})
                with KHOA:
                    v = DS_VIEC.get(m.group(1))
                if not v:
                    return self.gui(404, {"loi": "không có việc này"})
                moi = tao_viec(v["dau_vao"])
                xep_hang(moi)
                return self.gui(200, {"id": moi["id"]})
            if u.path == "/api/nguon":
                # chỉ trang của chính máy này được thêm/bớt trang được phép (trang ngoài không tự cho phép mình)
                if self._nguon[1] != "may":
                    return self.gui(403, {"loi": "chỉ đổi được từ http://127.0.0.1"})
                o = (d.get("nguon") or "").rstrip("/")
                if not nguon_hop_le(o):
                    raise ValueError("địa chỉ trang không hợp lệ (cần https://ten-mien)")
                ds = [x for x in doc_nguon() if x != o] + ([o] if d.get("them") else [])
                NGUON_CHO_PHEP.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
                return self.gui(200, {"nguon_cho_phep": ds})
            if u.path == "/api/cau_hinh":
                ds = {m["id"]: m for m in cd.DM["video"]}
                m = ds.get(d.get("id"))
                if not m:
                    raise ValueError("mô hình không hợp lệ")
                w, h = so(d.get("w"), 640, 128, 1280), so(d.get("h"), 352, 128, 1280)
                extra = [x for x in d.get("extra") or [] if x in ("--offload-to-cpu",)]
                cd.luu_cau_hinh(video={"id": m["id"], "w": w, "h": h, "extra": extra})
                return self.gui(200, cd.doc_cau_hinh())
            if u.path == "/api/xoa_tep":
                p = tham_chieu(d.get("ref"))
                p.unlink()
                return self.gui(200, {"ok": True})
            if u.path == "/api/mo_thu_muc":
                if self._nguon[1] != "may":
                    raise ValueError("chỉ mở được thư mục khi dùng giao diện ngay trên máy này")
                p = tham_chieu(d.get("ref")) if d.get("ref") else SP
                mo_thu_muc(p)
                return self.gui(200, {"ok": True})
        except ValueError as e:
            return self.gui(400, {"loi": str(e)})
        except Exception as e:
            return self.gui(500, {"loi": f"{type(e).__name__}: {e}"})
        self.gui(404, {"loi": "không có"})


def trang_cho_phep(nguon):
    """Trang trên chính máy này để người dùng cho phép một tên miền (vd bản triển khai trên Coolify) điều khiển máy."""
    ok = nguon_hop_le(nguon)
    e = lambda x: x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")  # noqa
    than = (f'''<p>Trang <b>{e(nguon)}</b> muốn dùng Xưởng phim trên máy này: xếp việc tạo video, lồng tiếng, ghép
phim, xem và tải tệp trong thư viện. Mọi việc vẫn chạy trên máy này; trang đó không lấy được tệp nào khác.</p>
<p>Chỉ cho phép nếu bạn biết và tin trang này (thường là bản Xưởng phim bạn tự triển khai).</p>
<p><button id="ok">Cho phép</button> <a href="/">Không, về Xưởng phim</a></p><p id="kq"></p>
<script>document.getElementById("ok").onclick=async()=>{{const t=(await (await fetch("/api/ket_noi")).json()).token;
const r=await fetch("/api/nguon",{{method:"POST",headers:{{"Content-Type":"application/json","X-Token":t}},
body:JSON.stringify({{nguon:{json.dumps(nguon)},them:true}})}});document.getElementById("kq").textContent=r.ok?
"Đã cho phép. Quay lại trang kia và bấm Thử lại.":"Không lưu được: "+(await r.json()).loi;}};</script>'''
            if ok else f"<p>Địa chỉ trang không hợp lệ: {e(nguon)}. Cần dạng https://ten-mien.</p>")
    return ('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><title>Cho phép trang dùng Xưởng phim</title><style>body{font:16px/1.6 system-ui,sans-serif;'
            'max-width:640px;margin:40px auto;padding:0 16px;color:#1f1d1a;background:#f6f4ef}button{font:inherit;'
            'padding:8px 18px;border-radius:8px;border:0;background:#c2562b;color:#fff;cursor:pointer}'
            '@media(prefers-color-scheme:dark){body{background:#171614;color:#ece8e1}a{color:#e07a4f}}</style>'
            f'<h1>Cho phép trang dùng Xưởng phim?</h1>{than}</html>')


def mo_thu_muc(p):
    """Mở trình quản lý tệp của hệ điều hành tại tệp/thư mục p."""
    if WIN:
        subprocess.Popen(["explorer", f"/select,{p}"] if p.is_file() else ["explorer", str(p)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)] if p.is_file() else ["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if p.is_file() else p)])


class MayChu(ThreadingHTTPServer):
    # Windows: SO_REUSEADDR cho hai chương trình cùng nghe một cổng; tắt đi để bản thứ hai phải nhận ra cổng bận
    allow_reuse_address = not WIN
    daemon_threads = True


def may_chu_dang_chay():
    """Cổng của một Xưởng phim khác đang chạy trên cùng thư mục này, hoặc None."""
    try:
        d = json.loads(TT_MAY_CHU.read_text(encoding="utf-8"))
        with urllib.request.urlopen(f"http://127.0.0.1:{int(d['cong'])}/api/trang_thai", timeout=2) as r:
            if json.load(r).get("thu_muc") == str(APP):
                return int(d["cong"])
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cong", type=int, default=8765, help="cổng (mặc định 8765; bận thì thử cổng kế tiếp)")
    ap.add_argument("--khong-mo", action="store_true", help="không tự mở trình duyệt")
    a = ap.parse_args()
    cu = may_chu_dang_chay()
    if cu:  # chỉ một bản chạy mỗi lúc, nếu không sẽ có hai việc nặng chạy song song
        url = f"http://127.0.0.1:{cu}/"
        print(f"Xuong phim da chay san: {url}", flush=True)
        if not a.khong_mo:
            webbrowser.open(url)
        return
    for loai in LOAI_TEP:
        (SP / loai).mkdir(parents=True, exist_ok=True)
    VIEC.mkdir(exist_ok=True)
    nap_viec_cu()
    threading.Thread(target=tho_lam, daemon=True).start()

    for cong in range(a.cong, a.cong + 20):
        try:
            sv = MayChu(("127.0.0.1", cong), XuLy)
            break
        except OSError:
            continue
    else:
        sys.exit("khong mo duoc cong nao")
    url = f"http://127.0.0.1:{cong}/"
    CONG["so"] = cong
    TT_MAY_CHU.write_text(json.dumps({"cong": cong, "pid": os.getpid(), "thu_muc": str(APP)}), encoding="utf-8")
    print(f"Xuong phim dang chay: {url}   (Ctrl+C de tat)", flush=True)
    print(f"Thu muc cong cu: {GOC}", flush=True)
    if not a.khong_mo:
        threading.Timer(0.8, webbrowser.open, (url,)).start()
    try:
        sv.serve_forever()
    except KeyboardInterrupt:
        print("dang tat; viec dang chay (neu co) se bi dung", flush=True)
        for vid in list(DANG_CHAY):
            huy(vid)
    finally:
        try:
            if json.loads(TT_MAY_CHU.read_text(encoding="utf-8")).get("pid") == os.getpid():
                TT_MAY_CHU.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
