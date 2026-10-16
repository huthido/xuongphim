# Hướng dẫn cài bộ công cụ làm phim ngắn bằng AI trên máy Windows (tạo cảnh, lồng tiếng, dựng phim)

Dành cho agent (Claude Code hoặc tương tự) được giao cài lên một máy Windows mới bộ công cụ đã dùng trên máy gốc để làm phim "Buổi họp gia đình" (65 giây) và cảnh "Hai bà cháu" (9 giây). Mọi thứ chạy cục bộ, không cần khoá API, không mất phí.

Làm lần lượt từng bước. Mỗi bước có phần **Kiểm tra**; chưa đạt thì dừng lại sửa, đừng làm tiếp. Xong thì báo người dùng theo mục cuối.

**Cách nhanh nhất (từ 16/10/2026):**
- `python xuong_phim/cai_dat.py kiem_may` kiểm tra máy và đề xuất mô hình hợp với máy.
- `python xuong_phim/cai_dat.py de_xuat` tải sd-cli và mô hình (kiểm SHA256), dựng lồng tiếng.

Các bước tự cài dưới đây vẫn đúng, dùng khi cần làm từng phần hoặc dựng phim bằng HyperFrames. Xem `AGENTS.md` và `xuong_phim/HUONG_DAN_XUONG_PHIM.md`.

**Mới (16/10/2026):**
- **Giao diện Xưởng phim** (`xuong_phim/`, bước 7): người dùng tạo video, lồng tiếng và ghép phim trên trình duyệt, không cần gõ lệnh.
  - Chạy trên **Windows, macOS, Linux**; chỉ cần Python 3.9+ và ffmpeg.
  - Hướng dẫn riêng: `xuong_phim/HUONG_DAN_XUONG_PHIM.md`.
- **Wan2.2 TI2V-5B tạo video từ ảnh:** giữ đúng mặt nhân vật trong ảnh, đẹp hơn hẳn Wan2.1. Xem Phần B của `tao_video_amd/HUONG_DAN_CAI_TAO_VIDEO_AMD.md`. Nên cài cả trên máy Intel, vì Wan2.2 chạy qua sd-cli Vulkan.
- Trên macOS và Linux, làm theo hướng dẫn này: bỏ qua lệnh `winget` (dùng `brew` / `apt`) và bản OpenVINO; dùng Phần B của hướng dẫn AMD.

## Bộ công cụ gồm những gì

```
lời mô tả ──► [1] Tạo cảnh: Wan2.1 1.3B ──► các clip 5 giây không tiếng ─┐
lời thoại ──► [2] Lồng tiếng: VieNeu-TTS ──► các câu .mp3 ───────────────┼─► [3] Dựng: HyperFrames ──► phim .mp4
                                                                         │      (chữ, phụ đề, chuyển cảnh, đồ hoạ)
                                                       [4] FilmCraft (tuỳ chọn: dựng bằng tay trên giao diện)
```

| Phần | Công cụ | Giấy phép | Mức kiểm chứng trên máy gốc |
|---|---|---|---|
| 1. Tạo cảnh | Wan2.1-T2V-1.3B, có **hai hướng dẫn riêng** theo loại GPU | Apache 2.0 | Bản Intel chạy thật nhiều lần. Bản AMD chạy thật qua Vulkan trên Iris Xe, **chưa thử trên GPU AMD** |
| 2. Lồng tiếng | VieNeu-TTS v3 Turbo `vieneu==3.8.3`, chạy CPU | Apache 2.0 | Đã cài và chạy thật theo đúng bước 3 dưới đây (15/10/2026) |
| 3. Dựng phim | HyperFrames `hyperframes@0.8.162` (HTML → MP4) | Apache 2.0 | Đã kết xuất thật cả hai phim mẫu |
| 4. Dựng bằng tay | FilmCraft 0.8.0 bản portable | MIT/Apache 2.0, đang alpha | Đã cài, mở được, dựng và xuất được bằng dòng lệnh |

Máy gốc: i7-1260P, Intel Iris Xe, 16 GB RAM, Windows 11.

## Thư mục `bo_cai_lam_phim` mang từ máy gốc sang

```
bo_cai_lam_phim/
  HUONG_DAN_CAI_LAM_PHIM.md        file này
  tao_video/                        phần 1, bản GPU Intel (6 file, có hướng dẫn riêng)
  tao_video_amd/                    phần 1, sd-cli: Wan2.1 cho GPU AMD và Wan2.2 5B cho mọi GPU (3 file, có hướng dẫn riêng)
  xuong_phim/                       giao diện trên trình duyệt cho cả bộ (bước 7, có hướng dẫn riêng)
  long_tieng/                       phần 2
    long_tieng.py                   script lồng tiếng
    long_tieng_lock.txt             phiên bản thư viện đã chạy được
    vi_du_loi.json                  2 câu thử
  mau_phim/
    ba_chau/                        phim mẫu 9 giây: index.html, media/ (2 clip + 4 câu thoại), loi.json, viec_canh.json
    buoi_hop/                       phim mẫu 65 giây: index.html, media/ (12 clip + 15 câu), loi.json, kich_ban_canh.py
```

Thiếu `tao_video/tao_video.py`, `tao_video/tao_video_lock.txt`, `tao_video_amd/tao_video_amd.ps1` hay `long_tieng/long_tieng.py` thì dừng và xin người dùng; đừng tự viết lại.

## Yêu cầu máy

| | Tối thiểu | Ghi chú |
|---|---|---|
| Hệ điều hành | Windows 10/11 64-bit | |
| RAM | 16 GB | Tạo cảnh cần khoảng 7–8 GB trống. Chạy **từng việc một**, đừng chạy song song |
| Ổ đĩa trống | 30 GB | Tạo cảnh 15–20 GB, lồng tiếng 1,5 GB, HyperFrames và Chrome khoảng 1 GB |
| GPU | Intel Iris Xe/Arc, hoặc AMD Radeon có Vulkan | Chỉ phần 1 cần GPU. Phần 2–4 chạy được trên mọi máy |
| Mạng | Cần khi cài | Sau khi cài thì làm phim không cần mạng, trừ font Google lần đầu kết xuất |

## Quy ước

- `<ROOT>` là thư mục cài, mặc định `C:/Users/<tên người dùng>/AI`. **Không dùng đường dẫn có dấu cách hay dấu tiếng Việt.**
- Lệnh viết cho **Git Bash** (đường dẫn dùng `/`), giống hai hướng dẫn tạo cảnh. Riêng lệnh chạy tách nền ở bước 5 viết cho PowerShell.
- Biến shell không giữ được giữa các lần gọi lệnh của agent; mỗi lệnh hãy viết thẳng đường dẫn.
- **Việc chạy lâu (trên 5 phút) phải tách hẳn khỏi agent** bằng `Start-Process` (mẫu ở bước 5) và ghi nhật ký ra file. Chạy trực tiếp dễ bị ngắt vì quá thời gian chờ hoặc vì máy thiếu RAM.

## Bước 0. Kiểm tra máy

```bash
node --version; uv --version; git --version; ffmpeg -version | head -1
powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select Name; Get-CimInstance Win32_OperatingSystem | % { 'RAM trong: {0:N1} GB' -f (`$_.FreePhysicalMemory/1MB) }"
```

**Kiểm tra:** biết máy có GPU Intel hay AMD (quyết định bản nào ở bước 2) và còn bao nhiêu RAM trống. Thiếu công cụ nào thì sang bước 1.

## Bước 1. Cài công cụ nền

Chỉ cài những gì bước 0 báo thiếu:

```bash
winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
```

**Kiểm tra:** mở cửa sổ dòng lệnh mới (để PATH cập nhật), chạy lại lệnh đầu của bước 0. `node --version` phải từ **v22** trở lên (máy gốc v24.15.0); FFmpeg máy gốc 9.0.2; uv máy gốc 0.11.29.

## Bước 2. Phần 1: tạo cảnh (Wan2.1)

Chép thư mục tương ứng vào `<ROOT>` rồi **làm theo hướng dẫn riêng trong đó**, đủ các bước kiểm tra:

| Máy có | Chép | Làm theo |
|---|---|---|
| GPU Intel (Iris Xe, Arc) | `tao_video/` → `<ROOT>/tao_video/` | `<ROOT>/tao_video/HUONG_DAN_CAI_TAO_VIDEO.md` |
| GPU AMD Radeon (hoặc không có GPU Intel) | `tao_video_amd/` → `<ROOT>/tao_video_amd/` | `<ROOT>/tao_video_amd/HUONG_DAN_CAI_TAO_VIDEO_AMD.md` |

Bản Intel có chế độ nhiều clip một lượt (`--jobs viec.json`). Mẫu `viec.json` của phim hai bà cháu ở `mau_phim/ba_chau/viec_canh.json`; trước khi chạy, sửa trường `out` thành đường dẫn trên máy mới.

**Kiểm tra:** như hướng dẫn riêng. Trên GPU AMD, phải báo người dùng số đo thời gian thật.

## Bước 3. Phần 2: lồng tiếng (VieNeu-TTS)

Chép `long_tieng/` vào `<ROOT>/long_tieng/`, rồi tạo môi trường Python riêng và cài đúng phiên bản đã thử:

```bash
cd C:/Users/<tên người dùng>/AI/long_tieng && uv venv env --python 3.11 && uv pip install --python env/Scripts/python.exe -r long_tieng_lock.txt
```

Môi trường khoảng 0,6 GB. Bản này **không cần PyTorch hay GPU**: VieNeu tự chạy bằng ONNX Runtime trên CPU.

Liệt kê giọng (lần đầu tải mô hình khoảng 0,76 GB về `C:/Users/<tên người dùng>/.cache/huggingface/hub`: `pnnbao-ump/VieNeu-TTS-v3-Turbo` và `OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX`):

```bash
cd C:/Users/<tên người dùng>/AI/long_tieng && PYTHONIOENCODING=utf-8 env/Scripts/python.exe -I long_tieng.py --giong
```

Thử 2 câu:

```bash
cd C:/Users/<tên người dùng>/AI/long_tieng && PYTHONIOENCODING=utf-8 env/Scripts/python.exe -I long_tieng.py --loi vi_du_loi.json --out thu
```

Các cảnh báo "To support symlinks on Windows…" và "unauthenticated requests to the HF Hub" là vô hại, bỏ qua.

**Kiểm tra:** kết quả có dạng (máy gốc):

```
nap mo hinh: 32s
ba1  2.16s  (sinh 1.1s)  Hè này bà dẫn cháu đi biển nhé.
chau1  1.58s  (sinh 0.8s)  Thật ạ? Cháu thích lắm, bà ơi!
```

và hai file `thu/ba1.mp3`, `thu/chau1.mp3` không câm. Kiểm tra bằng `ffmpeg -hide_banner -i thu/ba1.mp3 -af volumedetect -f null - 2>&1 | grep mean_volume`; máy gốc ra khoảng −19 dB. Dưới −50 dB là câm, coi như lỗi.

Cách dùng: viết `loi.json` gồm các dòng `{"ten", "giong", "cau", "cao_do"}`. `cao_do` là số nửa cung nâng giọng, giữ nguyên tốc độ; dùng 3 cho giọng trẻ em, vì VieNeu không có sẵn giọng trẻ em hay người già. Script in độ dài từng câu để đặt vào phim.

Giọng đã dùng trên máy gốc: người kể **Ngọc Linh** (nữ, Bắc, kể chuyện), ông **Thanh Bình** (nam, Bắc), bà **Đoan Trang** (nữ, Bắc), cháu **Trúc Ly** với `cao_do: 3`.

Ghi chú:
- VieNeu nhân bản được giọng từ đoạn ghi âm 3–8 giây. Chỉ nhân bản giọng của chính người dùng hoặc người đã đồng ý.

## Bước 4. Phần 3: dựng phim (HyperFrames)

HyperFrames chạy qua `npx`, không cần cài toàn cục. **Không cài plugin hay skill của HyperFrames vào Claude Code** trừ khi người dùng yêu cầu; đặt `HYPERFRAMES_SKIP_SKILLS=1` khi chạy `init`.

Chép `mau_phim/` vào `<ROOT>/hyperframes/`, rồi kiểm tra hệ thống và tải Chrome dùng để kết xuất:

```bash
cd C:/Users/<tên người dùng>/AI/hyperframes/ba_chau && npx -y hyperframes@0.8.162 doctor && npx -y hyperframes@0.8.162 browser ensure
```

`doctor` báo ✗ cho whisper-cpp, Kokoro, MusicGen và Docker là bình thường; đó là phần tuỳ chọn, không dùng tới. Phải có ✓ cho Node.js, FFmpeg, FFprobe và Chrome. Máy gốc đã có Chrome trong bộ đệm nên **chưa đo** dung lượng và thời gian tải Chrome lần đầu.

Kiểm tra và kết xuất phim mẫu 9 giây:

```bash
cd C:/Users/<tên người dùng>/AI/hyperframes/ba_chau && npx -y hyperframes@0.8.162 check && npx -y hyperframes@0.8.162 render --fps 24 --workers 4 -o renders/ba_chau_long_tieng.mp4
```

**Kiểm tra:**
- `check` kết thúc bằng `Check passed`.
- `render` in dạng `3.2 MB · 9.3s video · rendered in 35.5s` (số của máy gốc).
- `ffprobe -v error -show_entries stream=codec_type -of csv=p=0 renders/ba_chau_long_tieng.mp4` ra cả `video` và `audio`.

Sau đó kết xuất `buoi_hop` (65 giây) theo cùng cách. Máy gốc mất khoảng 1 phút 18 giây; trên máy chậm hơn hãy tách nền theo mẫu ở bước 5.

## Bước 5. Mẫu chạy tách nền (PowerShell)

Dùng cho việc lâu như tạo nhiều cảnh hay kết xuất phim dài. Ví dụ tạo cảnh bằng bản Intel:

```powershell
$V = "C:\Users\<tên người dùng>\AI\tao_video"
$cmd = "cd /d `"$V`" && env\Scripts\python.exe -I tao_video.py --jobs `"$V\viec.json`" > `"$V\log.txt`" 2>&1 & echo EXIT %errorlevel% >> `"$V\log.txt`""
Start-Process cmd.exe -ArgumentList "/c", $cmd -WindowStyle Hidden
```

Theo dõi `log.txt` cho tới khi có dòng `EXIT`. Muốn biết tiến trình còn sống không thì dùng `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`. Đừng dựa vào `Get-Process -Id`: trên máy gốc nó từng báo nhầm là tiến trình đã dừng.

**Đừng chạy lại song song** khi nghi tiến trình đã chết. Nếu máy vừa ngủ, tiến trình chỉ bị treo và sẽ chạy tiếp khi máy thức; lần chạy mới sẽ không ghi được vào cùng file nhật ký.

## Bước 6 (tuỳ chọn). Phần 4: FilmCraft

Chỉ cài khi người dùng muốn dựng bằng tay trên giao diện kiểu Premiere. Tải bản portable 0.8.0 từ trang phát hành chính thức, rồi đối chiếu mã kiểm tra:

```bash
mkdir -p C:/Users/<tên người dùng>/AI/filmcraft/tai && cd C:/Users/<tên người dùng>/AI/filmcraft/tai && curl -sSLO https://github.com/storytold/filmcraft/releases/download/v0.8.0/filmcraft-0.8.0-windows-x64-portable.zip && sha256sum filmcraft-0.8.0-windows-x64-portable.zip
```

**Kiểm tra:** mã phải là `0119afd59dfd6ecb94470ba6b3a48108ade87dabd4972898dd6c04e1db396b0b`. Khác thì xoá file và báo người dùng.

Sau đó giải nén vào `<ROOT>/filmcraft/app/`. Chữ ký số của `filmcraft.exe` phải hợp lệ, người ký `Learning Machines Inc`.

- Điều khiển bằng dòng lệnh: `filmcraft-cli.exe --project p.fcproj --save run lenh.jsonl` (mỗi dòng `{"id","params"}`); `filmcraft-cli.exe commands` liệt kê hơn 700 lệnh.
- Trên máy GPU AMD, nếu `filmcraft.exe` vừa mở đã tắt thì chạy với biến môi trường `WGPU_BACKEND=vulkan` (lỗi driver AMD có ghi trong README của FilmCraft).

## Bước 7. Giao diện Xưởng phim

Chép `xuong_phim/` vào `<ROOT>/xuong_phim/` (phải nằm cạnh `tao_video_amd/` và `long_tieng/`), rồi làm theo `<ROOT>/xuong_phim/HUONG_DAN_XUONG_PHIM.md`.

**Kiểm tra:** chạy `<ROOT>/long_tieng/env/Scripts/python.exe -I <ROOT>/xuong_phim/xuong_phim.py --khong-mo` (macOS/Linux: `.../env/bin/python`), rồi gọi `curl -s http://127.0.0.1:8765/api/trang_thai`. Các công cụ đã cài ở bước 2–3 phải có `"co": true`. Tắt ứng dụng sau khi kiểm tra; người dùng mở bằng `chay_xuong_phim.bat` hoặc `chay_xuong_phim.sh`.

Người dùng muốn agent tự làm phim thì đăng ký máy chủ MCP `xuong_phim/mcp_xuong_phim.py` (mục "Gắn agent qua MCP" trong `HUONG_DAN_XUONG_PHIM.md`). Kiểm tra bằng `claude mcp get xuong-phim`.

## Quy trình làm một phim

Người dùng không quen dòng lệnh thì dùng Xưởng phim (bước 7): ảnh → video → lồng tiếng → ghép. Cần phụ đề, thẻ tên, đồ hoạ thì dựng tiếp bằng HyperFrames như dưới đây.

1. **Kịch bản:** chia thành các cảnh 5 giây, mỗi cảnh **một hành động đơn giản**.
2. **Tạo cảnh:** viết `viec.json` (512×288, 81 khung, khoảng 5 phút mỗi cảnh trên máy gốc) → chạy tách nền → xem lưới khung hình:
   ```bash
   ffmpeg -i canh.mp4 -vf "select='not(mod(n\,10))',tile=3x3" -frames:v 1 luoi.png
   ```
   Cảnh hỏng thì sửa lời mô tả hoặc đổi `seed` rồi chạy lại riêng cảnh đó.
3. **Lồng tiếng:** viết `loi.json` → `long_tieng.py` → ghi lại độ dài từng câu.
4. **Dựng:** chép clip vào `media/`, câu thoại vào `media/loi/`, sửa `index.html` (lấy một phim mẫu làm khuôn) → `check` → `snapshot` xem khung → `render`.
5. **Kiểm tra file ra:**
   - Xem vài khung hình.
   - Dò khoảng lặng để chắc lời thoại vào đúng lúc: `ffmpeg -i phim.mp4 -af silencedetect=noise=-40dB:d=0.3 -vn -f null -`.
   - Báo người dùng nghe thử, vì agent không nghe được.

## Bài học từ máy gốc (đọc trước khi viết lời mô tả và dựng)

**Tạo cảnh (Wan2.1 1.3B):**
- **Cận cảnh một người làm tốt nhất**, kể cả người trông như thật.
- **Hai người khác tuổi trong cùng khung thì hỏng:** mô hình kéo hai người về giống nhau. Thử bà và cháu thì ra hai bé gái, lần sau ra hai phụ nữ trung niên. Cách đạt là tạo mỗi người một clip, rồi dựng cắt qua lại.
- Cảnh toàn có 4–6 người thường thiếu người, sai người, gần như đứng yên.
- Bàn tay hay hỏng: cho tay để yên, tránh động tác chạm tay.
- Mô hình hay bỏ qua chi tiết (kiểu tóc, phong cách hoạt hình, tuổi). Viết điều quan trọng nhất ở đầu câu.
- Phong cách giữ khá đều giữa các cảnh, nhưng **mặt nhân vật đổi từ cảnh này sang cảnh khác**. Đây là giới hạn của việc tạo video từ chữ.
- 0,1–0,3 giây đầu clip đôi khi giật (người hiện ra đột ngột): dùng `data-media-start="0.3"` khi dựng.
- Máy vào chế độ ngủ giữa chừng thì một bước có thể kéo dài hàng giờ. `tao_video.py` tự giữ máy thức khi để yên, nhưng **gập nắp vẫn ngủ**: dặn người dùng cắm sạc và không gập nắp.

**Dựng (HyperFrames):**
- **Không đặt `transform` (scale, GSAP zoom) lên `<video>`:** khi kết xuất, khung video bị lệch và có dải viền. Chỉ animate `opacity` cho video.
- Phần tử có `class="clip"` bị đặt kín khung (`inset:0`). Phụ đề phải ghi đè bằng `inset: auto auto 42px 50%; width: auto; height: auto; transform: translateX(-50%)`.
- Font tiếng Việt: dùng `Be Vietnam Pro` từ Google Fonts. HyperFrames tự tải về và nhúng cố định, dấu tiếng Việt hiển thị đúng.
- Cảnh báo `nested_structure_needs_subcomposition` và `clip_media_fit` của `check` là vô hại; `check` vẫn `passed`.
- GSAP tải từ CDN có kèm `integrity` (SRI); giữ nguyên dòng đó trong file mẫu.

**Lồng tiếng:**
- **Mỗi lần tạo lại, cùng một câu ra độ dài khác.** Ví dụ "Cháu thích lắm, bà ơi!" lần đầu 1,90 giây, lần sau 1,27 giây. Tạo lại câu nào thì sửa `data-duration` của thẻ `<audio>` tương ứng trong `index.html` theo độ dài mới mà `long_tieng.py` in ra, và chắc câu vẫn nằm gọn trong cảnh. Các file `.mp3` trong `mau_phim/*/media/loi/` là bản khớp sẵn với `index.html`.
- Khi đổi cao độ bằng ffmpeg, `asetrate` phải dùng đúng tần số lấy mẫu của file (VieNeu ra 48 kHz). Sai thì giọng trầm và chậm gấp đôi. `long_tieng.py` đã tự đọc tần số.

**Khác:**
- File lệnh có ngoặc kép cong “ ” thì viết bằng Python; chuỗi PowerShell coi chúng là dấu nháy.

## Số đo trên máy gốc

| Việc | Thời gian |
|---|---|
| Tạo 1 cảnh 512×288, 81 khung (5 giây), bản Intel | 4–5 phút (tạo chuyển động 191–298 giây, giải mã 21–65 giây) |
| Tạo 12 cảnh (60 giây phim), 4 đợt mỗi đợt 3 cảnh | 64 phút, gồm 6 phút máy ngủ |
| Lồng tiếng 1 câu ngắn bằng `long_tieng.py` | khoảng 1 giây, cộng 32 giây nạp mô hình mỗi lần chạy |
| Kết xuất HyperFrames 9,3 giây, có tiếng | 36 giây |
| Kết xuất HyperFrames 65 giây, có tiếng | 1 phút 18 giây |
| Bản AMD trên GPU AMD thật | **chưa đo** |
| Wan2.2 5B từ ảnh, 640×352, 49 khung (2 giây), qua Xưởng phim | 140 giây |
| Wan2.2 5B từ ảnh, 640×352, 121 khung (5 giây) | khoảng 10 phút |
| Lồng tiếng 2 câu qua Xưởng phim (gồm nạp mô hình) | 14 giây |
| Ghép phim 2 cảnh có lời thoại, 1280×720, qua Xưởng phim | 3 giây |
| Xưởng phim trên Linux | chạy được trong container Ubuntu 24.04 với sd-cli và VieNeu giả; GPU thật **chưa đo** |
| Xưởng phim trên macOS | **chưa đo** (chưa chạy thử) |

## Báo cáo cho người dùng sau khi cài

Liệt kê:
- Phần nào đã cài, chạy thật được tới bước kiểm tra nào.
- Số đo thời gian thật trên máy mới, nhất là tạo một cảnh 5 giây.
- Đường dẫn hai phim mẫu đã kết xuất lại.
- Phần nào bỏ qua và vì sao, ví dụ FilmCraft khi người dùng không cần.

Số nào chưa đo thì ghi "chưa đo", đừng ước đoán.
