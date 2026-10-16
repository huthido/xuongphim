"""Máy chủ MCP cho Xưởng phim: cho agent (Claude Code, Claude Desktop, Cursor, ...) điều khiển Xưởng phim.
Chỉ cần Python 3.9+ (thư viện chuẩn); chạy trên Windows, Linux, macOS. Giao tiếp MCP qua stdio (JSON-RPC mỗi dòng một tin).
Xem HUONG_DAN_XUONG_PHIM.md, mục "Gắn agent qua MCP".

  claude mcp add xuong-phim -- <python> -I <ROOT>/xuong_phim/mcp_xuong_phim.py

Mọi việc đi qua API của xuong_phim.py nên vẫn giữ quy tắc của ứng dụng: một việc mỗi lần, chờ đủ RAM, tệp chỉ trong
san_pham/. Xưởng phim chưa chạy thì tự mở (không mở trình duyệt); việc vẫn chạy tiếp khi agent thoát.
"""
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
import xuong_phim as xp  # noqa: E402  (chỉ dùng hằng số và hàm tiện ích, không chạy máy chủ)

PHIEN_BAN = "1.1.0"
GIAO_THUC = ["2025-06-18", "2025-03-26", "2024-11-05"]
_ket_noi = {"url": None, "token": None}
_GHI = threading.Lock()
_MO = threading.Lock()  # nhiều yêu cầu cùng lúc thì chỉ một yêu cầu được mở Xưởng phim


def log(*a):  # stdout dành riêng cho MCP; mọi thứ khác ghi ra stderr
    print(*a, file=sys.stderr, flush=True)


# ---------- nói chuyện với xuong_phim.py ----------

def _cong():
    try:
        return int(json.loads(xp.TT_MAY_CHU.read_text(encoding="utf-8"))["cong"])
    except Exception:
        return None


def _song(url):
    try:
        with urllib.request.urlopen(url + "api/trang_thai", timeout=3) as r:
            return json.load(r).get("thu_muc") == str(APP)
    except Exception:
        return False


def ket_noi():
    """URL của Xưởng phim đang chạy; chưa chạy thì mở nền và chờ tối đa 20 giây."""
    if _ket_noi["url"] and _song(_ket_noi["url"]):
        return _ket_noi["url"]
    with _MO:
        return _mo_xuong_phim()


def _mo_xuong_phim():
    c = _cong()
    if not (c and _song(f"http://127.0.0.1:{c}/")):
        log("Xuong phim chua chay, dang mo nen...")
        kw = {"creationflags": 0x00000008 | 0x00000200 | 0x08000000} if xp.WIN else {"start_new_session": True}
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW: sống tiếp khi agent thoát
        with open(APP / "may_chu_log.txt", "ab") as f:
            subprocess.Popen([sys.executable, "-I", str(APP / "xuong_phim.py"), "--khong-mo"], cwd=str(APP),
                             stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        for _ in range(40):
            time.sleep(0.5)
            c = _cong()
            if c and _song(f"http://127.0.0.1:{c}/"):
                break
        else:
            raise RuntimeError(f"không mở được Xưởng phim; xem {APP / 'may_chu_log.txt'}")
    _ket_noi.update(url=f"http://127.0.0.1:{c}/", token=None)
    return _ket_noi["url"]


def _token(url):
    if not _ket_noi["token"]:
        with urllib.request.urlopen(url + "api/ket_noi", timeout=5) as r:
            _ket_noi["token"] = json.load(r)["token"]
    return _ket_noi["token"]


def goi(duong, du_lieu=None, than=None, thu_lai=True):
    """GET (du_lieu None) hoặc POST JSON / POST thân nhị phân tới API Xưởng phim."""
    url = ket_noi()
    if du_lieu is None and than is None:
        req = urllib.request.Request(url + duong)
    else:
        if than is None:
            than = json.dumps(du_lieu).encode("utf-8")
        req = urllib.request.Request(url + duong, data=than, method="POST",
                                     headers={"X-Token": _token(url), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        loi = json.loads(e.read() or b"{}").get("loi", str(e))
        if e.code == 403 and thu_lai:  # Xưởng phim khởi động lại thì mã đổi
            _ket_noi["token"] = None
            return goi(duong, du_lieu, than, False)
        raise ValueError(loi)


# ---------- tiện ích ----------

def tep_tu_ref(ref):
    return xp.tham_chieu(ref)


def tom_tat_viec(v):
    x = {k: v.get(k) for k in ("id", "loai", "tieu_de", "trang_thai", "ma", "cho_ram") if v.get(k) is not None}
    if v.get("bat_dau"):
        x["da_chay_giay"] = round((v.get("ket_thuc") or time.time()) - v["bat_dau"])
    if v.get("ra"):
        x["ket_qua"] = [{"ref": r, "duong_dan": str(tep_tu_ref(r))} for r in v["ra"]]
    return x


def anh_xem(p, kieu):
    """Ảnh JPEG (base64) để agent tự xem: ảnh thu nhỏ, hoặc lưới 6 khung trải đều của video."""
    ff = xp.tim_ffmpeg()
    if not ff:
        raise ValueError("chưa cài ffmpeg")
    if kieu == "anh":
        vf = "scale='min(1024,iw)':-2"
    else:
        fp = str(Path(ff).with_name(Path(ff).name.replace("ffmpeg", "ffprobe")))
        d = float(subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                 capture_output=True, text=True, check=True).stdout.strip() or 1)
        vf = f"fps={6 / max(d, 0.2):.5f},scale=512:-2,tile=3x2"
    r = subprocess.run([ff, "-v", "error", "-i", str(p), "-vf", vf, "-frames:v", "1", "-q:v", "4",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True, check=True)
    return base64.b64encode(r.stdout).decode("ascii")


def do_dai(p):
    ff = xp.tim_ffmpeg()
    fp = str(Path(ff).with_name(Path(ff).name.replace("ffmpeg", "ffprobe")))
    r = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", str(p)],
                       capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    ra = {"giay": round(float(d.get("format", {}).get("duration", 0)), 2)}
    for s in d.get("streams", []):
        if s.get("width"):
            ra["co"] = f"{s['width']}x{s['height']}"
    return ra


# ---------- công cụ ----------

def ct_trang_thai(a):
    s = goi("api/trang_thai")
    return {"xuong_phim": _ket_noi["url"], "he_dieu_hanh": s["he_dieu_hanh"], "ram_gb": s["ram"],
            "cong_cu": {k: (True if v["co"] else v["ly_do"]) for k, v in s["cong_cu"].items() if isinstance(v, dict)},
            "mo_hinh_video_da_cai": [m["id"] for m in s["cong_cu"].get("mo_hinh_video", [])],
            "ung_dung_chiem_ram": s.get("an_ram") or None,
            "viec_gan_day": [tom_tat_viec(v) for v in s["viec"][:int(a.get("so_viec", 10))]]}


def ct_danh_sach_tep(a):
    ds = goi("api/tep")
    if a.get("loai"):
        ds = [f for f in ds if f["loai"] == a["loai"] or f["kieu"] == a["loai"]]
    return [{"ref": f["ref"], "kieu": f["kieu"], "kb": round(f["co"] / 1024),
             "luc": time.strftime("%d/%m %H:%M", time.localtime(f["luc"])), "duong_dan": str(tep_tu_ref(f["ref"]))}
            for f in ds[:int(a.get("toi_da", 50))]]


def ct_danh_sach_giong(a):
    return goi("api/giong")


def ct_tao_anh(a):
    return {"id": goi("api/viec", dict(a, loai="anh"))["id"], "ghi_chu": "khoảng 1,5 phút mỗi ảnh; dùng cho_viec"}


def ct_tao_video(a):
    d = dict(a, loai="video")
    mh = d.get("mo_hinh", "wan22")
    if d.get("giay") and not d.get("frames"):
        fps = 24 if mh == "wan22" else 16
        d["frames"] = round(float(d.pop("giay")) * fps / 4) * 4 + 1
    return {"id": goi("api/viec", d)["id"],
            "ghi_chu": "Wan2.2 640x352: 2 giây khoảng 2,5 phút, 5 giây khoảng 10 phút trên Iris Xe; dùng cho_viec"}


def ct_long_tieng(a):
    return {"id": goi("api/viec", {"loai": "tieng", "dong": a["dong"]})["id"],
            "ghi_chu": "khoảng 15 giây cho vài câu; dùng cho_viec"}


def ct_ghep_phim(a):
    return {"id": goi("api/viec", dict(a, loai="ghep"))["id"], "ghi_chu": "vài giây; dùng cho_viec"}


def ct_xem_viec(a):
    v = goi(f"api/viec/{a['id']}")
    x = tom_tat_viec(v)
    x["nhat_ky_cuoi"] = (v.get("log") or "")[-int(a.get("so_ky_tu", 1500)):]
    return x


def ct_cho_viec(a):
    het = time.time() + min(float(a.get("toi_da_giay", 300)), 1800)
    while True:
        v = goi(f"api/viec/{a['id']}")
        if v["trang_thai"] not in ("cho", "dang_chay"):
            x = tom_tat_viec(v)
            if v["trang_thai"] != "xong":
                x["nhat_ky_cuoi"] = (v.get("log") or "")[-1500:]
            return x
        if time.time() >= het:
            x = tom_tat_viec(v)
            x["ghi_chu"] = "chưa xong; gọi cho_viec lần nữa để chờ tiếp"
            x["nhat_ky_cuoi"] = (v.get("log") or "")[-400:]
            return x
        time.sleep(3)


def ct_huy_viec(a):
    return goi(f"api/viec/{a['id']}/huy", {})


def ct_chay_lai(a):
    return goi(f"api/viec/{a['id']}/chay_lai", {})


def ct_chay_luon(a):
    return goi(f"api/viec/{a['id']}/chay_luon", {})


def ct_tai_len(a):
    p = Path(a["duong_dan"]).expanduser()
    if not p.is_file():
        raise ValueError(f"không thấy tệp {p}")
    q = urllib.parse.quote(p.name)
    return goi(f"api/tai_len?ten={q}", than=p.read_bytes())


def ct_xem_tep(a):
    p = tep_tu_ref(a["ref"])
    kieu = xp.kieu_tep(p)
    info = dict(do_dai(p) if kieu != "anh" else {}, ref=a["ref"], duong_dan=str(p), kieu=kieu)
    if kieu in ("anh", "video"):
        if kieu == "video":
            info["ghi_chu"] = "lưới 3x2: 6 khung trải đều từ đầu đến cuối clip, đọc từ trái sang phải, trên xuống dưới"
        return [{"type": "text", "text": json.dumps(info, ensure_ascii=False)},
                {"type": "image", "data": anh_xem(p, kieu), "mimeType": "image/jpeg"}]
    info["ghi_chu"] = "tệp âm thanh: agent không nghe được, hãy nhờ người dùng nghe thử"
    return info


def ct_kiem_may(a):
    d = goi("api/may" + ("?moi=1" if a.get("lam_moi") else ""))
    return {"may": d["may"], "bo_nho_cho_video_gb": d["ngan_sach_gb"], "giai_thich": d["ngan_sach_mo_ta"],
            "de_xuat_video": d["video"], "phuong_an_khac": d["phuong_an_khac"], "canh_bao": d["canh_bao"],
            "long_tieng": d["tieng"], "tao_anh": d["anh"],
            "ghi_chu": "Số bộ nhớ chỉ đo thật trên Intel Iris Xe 16 GB; 'da_thu': false nghĩa là ước lượng. Hỏi người dùng "
                       "trước khi tải (vài GB); cài bằng cai_dat."}


def ct_danh_muc_mo_hinh(a):
    d = goi("api/mo_hinh")
    return {"video": [{k: m.get(k) for k in ("id", "ten", "ho", "mo_ta", "bo_nho_gb", "nguon_so", "da_thu", "da_cai",
                                             "can_tai_gb")} for m in d["video"]],
            "kich_thuoc": d["kich_thuoc"], "mac_dinh": (d.get("cau_hinh") or {}).get("video")}


def ct_cai_dat(a):
    lenh = a["lenh"]
    ts = [str(x) for x in a.get("tham_so") or []]
    return {"id": goi("api/viec", {"loai": "cai", "lenh": lenh, "tham_so": ts})["id"],
            "ghi_chu": "việc tải/cài chạy trong hàng đợi (mô hình vài GB có thể mất nhiều phút); dùng cho_viec, "
                       "rồi trang_thai để thấy công cụ mới"}


def ct_dat_mac_dinh(a):
    return goi("api/cau_hinh", {"id": a["id"], "w": a["w"], "h": a["h"], "extra": a.get("extra") or []})


def ct_xoa_tep(a):
    return goi("api/xoa_tep", {"ref": a["ref"]})


S_REF = {"type": "string", "description": "tệp trong thư viện, dạng 'loai/ten' lấy từ danh_sach_tep (vd 'anh/x.png')"}
S_ID = {"type": "string", "description": "mã việc, trả về khi tạo việc"}
CONG_CU = [
    ("trang_thai", "Xem Xưởng phim: công cụ nào đã cài, RAM trống, các việc gần đây. Gọi đầu tiên.",
     {"so_viec": {"type": "integer", "description": "số việc gần nhất cần xem, mặc định 10"}}, [], ct_trang_thai, True),
    ("danh_sach_tep", "Liệt kê ảnh/video/tiếng/phim trong thư viện (mới nhất trước), kèm 'ref' để dùng cho việc khác "
     "và đường dẫn trên đĩa.",
     {"loai": {"type": "string", "enum": ["anh", "video", "tieng", "phim", "tai_len"],
               "description": "lọc theo thư mục hoặc kiểu tệp"},
      "toi_da": {"type": "integer", "description": "mặc định 50"}}, [], ct_danh_sach_tep, True),
    ("danh_sach_giong", "Liệt kê giọng đọc tiếng Việt của VieNeu (dùng trường 'ma' cho long_tieng).", {}, [],
     ct_danh_sach_giong, True),
    ("tao_anh", "Xếp việc tạo ảnh nhân vật (FLUX.2 klein). Lời mô tả bằng tiếng Anh; cận cảnh một người, nhìn vào "
     "máy, tay để yên. Trả về id việc.",
     {"prompt": {"type": "string"}, "w": {"type": "integer", "description": "mặc định 1248"},
      "h": {"type": "integer", "description": "mặc định 720"},
      "so_anh": {"type": "integer", "description": "1-8, mỗi ảnh một seed liên tiếp; mặc định 1"},
      "seed": {"type": "integer"}, "ref": dict(S_REF, description="ảnh tham chiếu (tuỳ chọn)")},
     ["prompt"], ct_tao_anh, False),
    ("tao_video", "Xếp việc tạo video. Có 'anh' thì nhân vật trong ảnh chuyển động (Wan2.2 5B, giữ đúng mặt). "
     "Lời mô tả tiếng Anh, kể động tác theo thứ tự; mỗi clip một người. Trả về id việc.",
     {"prompt": {"type": "string"}, "anh": dict(S_REF, description="ảnh khung đầu (chỉ wan22)"),
      "mo_hinh": {"type": "string", "description": "id trong danh_muc_mo_hinh (vd wan22_5b_q4); bỏ trống = mô hình "
                  "mặc định đã chọn cho máy; 'wan21_ov' = bản OpenVINO cho máy Intel"},
      "w": {"type": "integer", "description": "mặc định 640 (máy 16 GB RAM); 832 cần ≥32 GB"},
      "h": {"type": "integer", "description": "mặc định 352"},
      "giay": {"type": "number", "description": "độ dài 2-5 giây (đổi ra số khung); mặc định 5"},
      "frames": {"type": "integer", "description": "số khung (4k+1), thay cho giay"},
      "seed": {"type": "integer"}}, ["prompt"], ct_tao_video, False),
    ("long_tieng", "Xếp việc đọc lời thoại tiếng Việt thành các tệp .mp3 (mỗi câu một tệp). Trả về id việc.",
     {"dong": {"type": "array", "items": {"type": "object", "properties": {
         "giong": {"type": "string", "description": "mã giọng từ danh_sach_giong; trống = mặc định"},
         "cau": {"type": "string"},
         "cao_do": {"type": "number", "description": "nửa cung, -12..12; giọng trẻ em: giọng nữ +3"}},
         "required": ["cau"]}}}, ["dong"], ct_long_tieng, False),
    ("ghep_phim", "Xếp việc ghép các clip thành phim .mp4, mỗi cảnh kèm một câu thoại (tuỳ chọn), thêm nhạc nền.",
     {"canh": {"type": "array", "items": {"type": "object", "properties": {
         "video": S_REF, "tieng": dict(S_REF, description="câu thoại (tuỳ chọn)"),
         "tre": {"type": "number", "description": "giây sau đầu cảnh thì nói; mặc định 0"},
         "bo_dau": {"type": "number", "description": "cắt bỏ bao nhiêu giây đầu clip"}}, "required": ["video"]}},
      "nhac": dict(S_REF, description="nhạc nền (tuỳ chọn)"),
      "am_luong_nhac": {"type": "number", "description": "0-1, mặc định 0.15"},
      "w": {"type": "integer", "description": "mặc định 1280"}, "h": {"type": "integer", "description": "mặc định 720"},
      "ten": {"type": "string", "description": "tên tệp phim"}}, ["canh"], ct_ghep_phim, False),
    ("cho_viec", "Chờ một việc xong (hoặc hết thời gian chờ) rồi trả kết quả: trạng thái, tệp ra, nhật ký nếu lỗi.",
     {"id": S_ID, "toi_da_giay": {"type": "number", "description": "mặc định 300, tối đa 1800"}}, ["id"],
     ct_cho_viec, True),
    ("xem_viec", "Xem trạng thái và cuối nhật ký của một việc (không chờ).",
     {"id": S_ID, "so_ky_tu": {"type": "integer", "description": "mặc định 1500"}}, ["id"], ct_xem_viec, True),
    ("xem_tep", "Xem một tệp trong thư viện: ảnh thì trả ảnh thu nhỏ; video thì trả lưới 6 khung hình trải đều để "
     "đánh giá chất lượng; âm thanh thì trả độ dài.", {"ref": S_REF}, ["ref"], ct_xem_tep, True),
    ("tai_len", "Đưa một tệp trên máy (ảnh, video, âm thanh) vào thư viện; trả về ref.",
     {"duong_dan": {"type": "string", "description": "đường dẫn tuyệt đối tới tệp"}}, ["duong_dan"], ct_tai_len, False),
    ("huy_viec", "Huỷ việc đang chờ hoặc đang chạy (dừng cả sd-cli, ffmpeg bên dưới).", {"id": S_ID}, ["id"],
     ct_huy_viec, False),
    ("chay_lai", "Tạo lại việc với cùng thông số (dùng khi việc lỗi hoặc bị ngắt).", {"id": S_ID}, ["id"],
     ct_chay_lai, False),
    ("chay_luon", "Cho việc đang 'chờ RAM' chạy ngay dù RAM trống chưa đủ. Chỉ dùng khi người dùng đồng ý: máy có thể "
     "chậm hoặc đơ.", {"id": S_ID}, ["id"], ct_chay_luon, False),
    ("kiem_may", "Kiểm tra cấu hình máy (CPU, RAM, GPU và bộ nhớ GPU, ổ đĩa) và đề xuất mô hình video + kích thước hợp "
     "với máy để có chất lượng tốt nhất. Gọi khi cài máy mới hoặc người dùng hỏi nên dùng mô hình nào.",
     {"lam_moi": {"type": "boolean", "description": "đọc lại máy thay vì dùng kết quả lưu đệm 10 phút"}}, [], ct_kiem_may,
     True),
    ("danh_muc_mo_hinh", "Danh mục mô hình video: đã tải chưa, cần tải bao nhiêu GB, mô hình mặc định đang dùng.", {}, [],
     ct_danh_muc_mo_hinh, True),
    ("cai_dat", "Xếp việc cài đặt vào hàng đợi. lenh: 'de_xuat' (cài đúng đề xuất của kiem_may: sd-cli, mô hình, lồng "
     "tiếng, đặt làm mặc định), 'mo_hinh' (tham_so: [id, '--mac_dinh', '--w', '640', '--h', '352']), 'sd_cli' "
     "(tham_so: ['--ban', 'vulkan'|'cpu'|'cuda'|'rocm'|'metal']), 'long_tieng', 'tu_khoi_dong' (tham_so: ['bat'|'tat']: "
     "Xưởng phim tự chạy khi đăng nhập máy). Tải nhiều GB: hỏi người dùng trước.",
     {"lenh": {"type": "string", "enum": ["de_xuat", "mo_hinh", "sd_cli", "long_tieng", "tu_khoi_dong"]},
      "tham_so": {"type": "array", "items": {"type": "string"}}}, ["lenh"], ct_cai_dat, False),
    ("dat_mac_dinh", "Đặt mô hình video mặc định (đã tải) và kích thước cho máy này.",
     {"id": {"type": "string"}, "w": {"type": "integer"}, "h": {"type": "integer"},
      "extra": {"type": "array", "items": {"type": "string"}, "description": "vd ['--offload-to-cpu'] theo kiem_may"}},
     ["id", "w", "h"], ct_dat_mac_dinh, False),
    ("xoa_tep", "Xoá hẳn một tệp khỏi thư viện (không khôi phục được). Chỉ dùng khi người dùng yêu cầu.",
     {"ref": S_REF}, ["ref"], ct_xoa_tep, False),
]
BANG = {t[0]: t for t in CONG_CU}

HUONG_DAN = """Xưởng phim làm phim ngắn trên máy người dùng: tao_anh -> tao_video (từ ảnh) -> long_tieng -> ghep_phim.
- Gọi trang_thai trước để biết công cụ nào dùng được.
- Máy mới hoặc thiếu công cụ: gọi kiem_may để xem cấu hình và mô hình đề xuất, nói cho người dùng (tên mô hình, kích
  thước, dung lượng tải, cảnh báo), được đồng ý thì cai_dat lenh='de_xuat' rồi cho_viec. Không cần đăng nhập; mọi
  thứ chạy trên máy người dùng.
- Mỗi lần chỉ chạy một việc; việc mới xếp hàng. Thiếu RAM thì việc 'chờ RAM' và trang_thai chỉ ra ứng dụng chiếm RAM;
  hỏi người dùng đóng bớt, đừng tự gọi chay_luon.
- Tạo việc xong dùng cho_viec để chờ, rồi xem_tep để tự xem ảnh/khung hình trước khi dùng tiếp.
- Lời mô tả ảnh/video viết tiếng Anh; mỗi clip một người, cận cảnh, tay để yên; kể động tác theo thứ tự.
- Hai người khác tuổi trong một khung bị làm giống nhau: tạo mỗi người một clip rồi ghép xen kẽ.
- Chỉ dựng hình và lồng giọng người thật khi người đó đồng ý; không làm video giả mạo.
- Agent không nghe được tiếng: nhờ người dùng nghe thử phim."""


# ---------- JSON-RPC qua stdio ----------

def tra_loi(id_, ket_qua=None, loi=None):
    m = {"jsonrpc": "2.0", "id": id_}
    if loi:
        m["error"] = loi
    else:
        m["result"] = ket_qua
    with _GHI:
        sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def xu_ly(m):
    pp, id_, ts = m.get("method"), m.get("id"), m.get("params") or {}
    if pp == "initialize":
        ban = ts.get("protocolVersion")
        return {"protocolVersion": ban if ban in GIAO_THUC else GIAO_THUC[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "xuong-phim", "title": "Xưởng phim", "version": PHIEN_BAN},
                "instructions": HUONG_DAN}
    if pp == "ping":
        return {}
    if pp == "tools/list":
        return {"tools": [{"name": t, "title": t.replace("_", " "), "description": mo_ta,
                           "inputSchema": {"type": "object", "properties": tc, "required": bat_buoc},
                           "annotations": {"readOnlyHint": chi_doc, "destructiveHint": t in ("xoa_tep", "huy_viec"),
                                           "openWorldHint": False}}
                          for t, mo_ta, tc, bat_buoc, _, chi_doc in CONG_CU]}
    if pp == "tools/call":
        t = BANG.get(ts.get("name"))
        if not t:
            raise LookupError(f"không có công cụ {ts.get('name')}")
        try:
            kq = t[4](ts.get("arguments") or {})
            noi_dung = kq if isinstance(kq, list) and kq and isinstance(kq[0], dict) and "type" in kq[0] \
                else [{"type": "text", "text": json.dumps(kq, ensure_ascii=False, indent=1)}]
            return {"content": noi_dung, "isError": False}
        except Exception as e:  # lỗi của việc (thông số sai, thiếu công cụ...) trả về cho agent đọc
            return {"content": [{"type": "text", "text": f"Lỗi: {e}"}], "isError": True}
    raise LookupError(f"không hỗ trợ {pp}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    for dong in sys.stdin.buffer:
        dong = dong.strip()
        if not dong:
            continue
        try:
            m = json.loads(dong.decode("utf-8"))
        except ValueError:
            tra_loi(None, loi={"code": -32700, "message": "JSON lỗi"})
            continue
        for x in (m if isinstance(m, list) else [m]):
            if "id" not in x:  # thông báo (notifications/initialized, cancelled...): không trả lời
                continue
            # mỗi yêu cầu một luồng: cho_viec chờ lâu không chặn ping hay lệnh khác
            threading.Thread(target=chay_yeu_cau, args=(x,), daemon=True).start()


def chay_yeu_cau(x):
    try:
        tra_loi(x["id"], xu_ly(x))
    except LookupError as e:
        tra_loi(x["id"], loi={"code": -32601, "message": str(e)})
    except Exception as e:
        tra_loi(x["id"], loi={"code": -32603, "message": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
