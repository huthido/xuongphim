# Hướng dẫn cài và dùng công cụ tạo video clip từ lời mô tả cho máy GPU Intel (Wan2.1, OpenVINO)

Dành cho agent (Claude Code hoặc tương tự) được giao cài công cụ `tao_video.py` lên một máy Windows có **GPU Intel** (Iris Xe, Arc), dùng đúng mô hình và phiên bản thư viện đã chạy tốt trên máy gốc. Máy dùng **GPU AMD Radeon** (hoặc không có GPU Intel) thì dùng `HUONG_DAN_CAI_TAO_VIDEO_AMD.md`.

Công cụ chạy cục bộ, không cần mạng sau khi cài, không cần khoá API. Tạo ra **video chuyển động thật** (người đi, cây lay, mây trôi), dài 1–5 giây mỗi clip, không có tiếng.

Làm lần lượt từng bước. Mỗi bước có phần **Kiểm tra**; chưa đạt thì dừng lại sửa, đừng làm tiếp.

## Tóm tắt

| | |
|---|---|
| Kết quả | `<ROOT>/tao_video/env/Scripts/python.exe -I <ROOT>/tao_video/tao_video.py --prompt "..." --out clip.mp4` tạo được clip .mp4 (H.264) |
| Mô hình | Wan2.1-T2V-1.3B đã gộp LoRA CausVid (4 bước), chuyển sang OpenVINO int4: `liuming9157/Wan2.1-T2V-1.3B-Diffusers-ov-int4`, bản `821bbdc4313add7f129deecbf5e56ef682df752d` (4,4 GB, Apache 2.0) |
| Giải mã khung hình | TAEHV `taew2_1` (MIT, 22 MB). Tuỳ chọn `--vae-day-du` dùng VAE gốc `Wan-AI/Wan2.1-T2V-1.3B-Diffusers` (tải thêm 0,5 GB khi dùng lần đầu) |
| Mã chạy mô hình | `ov_wan_helper.py` từ OpenVINO notebooks, commit `3a243c5ee20a6192ba571b1b2c0702a59898502e` (Apache 2.0) |
| Python | 3.11, môi trường riêng `tao_video/env` tạo bằng `uv`, thư viện ghim trong `tao_video_lock.txt` |
| Clip ra | Mặc định 832×480, 33 khung hình, 16 khung/giây = khoảng 2 giây |
| Thời gian (máy gốc) | Khoảng 9 phút một clip mặc định (832×480, 2 giây); clip 512×288 dài 1 giây chỉ mất 24 giây tạo chuyển động |

Các bước dưới đây đã chạy thật trên máy gốc ngày 14/10/2026 (i7-1260P, Intel Iris Xe, 16 GB RAM, Windows 11).

## Sáu file mang từ máy gốc sang

Lấy từ `<ROOT>\tao_video\` trên máy gốc:

| File | Byte | SHA256 (16 ký tự đầu) | Vai trò |
|---|---|---|---|
| `tao_video.py` | 6873 | `7f2e80464104af58` | Script tạo clip (bản 15/10/2026, có giữ máy không tự ngủ khi chạy) |
| `ov_wan_helper.py` | 23411 | `ff4756a76805991` | Mã chạy Wan bằng OpenVINO |
| `taehv.py` | 26475 | `99545f093b36c162` | Bộ giải mã nhanh TAEHV |
| `taew2_1.safetensors` | 22642902 | `04766eac0221b539` | Trọng số TAEHV cho Wan2.1 |
| `tao_video_lock.txt` | 2552 | `75affb5b5ae9a5af` | Danh sách phiên bản thư viện |
| `HUONG_DAN_CAI_TAO_VIDEO.md` | | | File này |

`tao_video.py` và `tao_video_lock.txt` thì phải lấy từ máy gốc; thiếu thì dừng và xin người dùng, đừng tự viết lại. Ba file còn lại tải được nếu thiếu (bước 3).

## Yêu cầu máy

| | Tối thiểu | Ghi chú |
|---|---|---|
| Hệ điều hành | Windows 10/11 64-bit | |
| RAM | 16 GB | GPU Intel dùng chung RAM. Khi chạy cần khoảng 8 GB trống |
| Ổ đĩa trống | 20 GB | Mô hình 4,4 GB, môi trường Python 2,2 GB, bộ đệm biên dịch `ov_cache` tới 5 GB (mỗi cỡ khung hình mới thêm một bản; xoá được), bộ đệm tải của uv |
| GPU | Intel Iris Xe hoặc Intel Arc | Không có GPU Intel thì dùng bản AMD/Vulkan. OpenVINO không dùng GPU AMD hay NVIDIA |
| Mạng | Cần khi cài | |

## Quy ước

- `<ROOT>` là thư mục cài. Mặc định `C:/Users/<tên người dùng>/AI`. Người dùng chỉ định chỗ khác thì dùng chỗ đó. **Không dùng đường dẫn có dấu cách hay dấu tiếng Việt.**
- Lệnh viết cho **Git Bash**, đường dẫn dùng `/` (dấu `\` bị nuốt trong Git Bash). Biến như `V=...` không giữ được giữa các lần gọi lệnh của agent; mỗi lệnh hãy đặt lại hoặc viết thẳng đường dẫn.
- Bố cục phải đúng như sau, vì `tao_video.py` tìm các file cạnh nó:

```
<ROOT>/tao_video/
  tao_video.py
  ov_wan_helper.py
  taehv.py
  taew2_1.safetensors
  tao_video_lock.txt
  HUONG_DAN_CAI_TAO_VIDEO.md
  env/          (bước 4)
  ov_cache/     (tự tạo ở lần chạy đầu)
```

Nếu máy đã cài công cụ tạo ảnh `tao_anh.py` (`HUONG_DAN_CAI_TAO_ANH.md`) thì hai công cụ dùng chung bộ đệm Hugging Face nhưng **môi trường Python riêng**; cài công cụ này không ảnh hưởng công cụ kia.

## Bước 0. Kiểm tra máy và hỏi người dùng

PowerShell:

```powershell
(Get-CimInstance Win32_Processor).Name
(Get-CimInstance Win32_VideoController).Name
"RAM tong: {0} GB" -f [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
"RAM trong: {0} GB" -f [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)
Get-PSDrive C | Select-Object @{n='TrongGB';e={[math]::Round($_.Free/1GB)}}
```

**Kiểm tra:** có GPU Intel (Iris Xe / Arc), RAM tổng từ 16 GB, ổ trống từ 20 GB. Không có GPU Intel thì chuyển sang `HUONG_DAN_CAI_TAO_VIDEO_AMD.md`. Báo người dùng cấu hình máy và xin xác nhận `<ROOT>` trước khi cài.

## Bước 1. Cài uv và Git

```powershell
winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
```

Không có `winget` thì cài uv bằng `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`. Cài xong phải **mở cửa sổ dòng lệnh mới** để PATH cập nhật. Không cần cài Python hay ffmpeg riêng: uv tự tải Python 3.11, còn ffmpeg đi kèm thư viện `imageio-ffmpeg`.

**Kiểm tra:** `uv --version` và `git --version` in ra phiên bản (máy gốc: uv 0.9.8).

## Bước 2. Đặt các file vào `<ROOT>/tao_video`

```bash
V=C:/Users/<tên người dùng>/AI/tao_video      # sửa cho đúng
mkdir -p "$V"
# chép sáu file ở trên vào "$V"
ls -l "$V"
```

**Kiểm tra:** thấy đủ các file, kích thước khớp bảng ở trên.

## Bước 3. Tải các file mã còn thiếu (bỏ qua nếu đã chép đủ)

```bash
cd "$V"
curl -fL -o ov_wan_helper.py https://raw.githubusercontent.com/openvinotoolkit/openvino_notebooks/3a243c5ee20a6192ba571b1b2c0702a59898502e/notebooks/wan2.1-text-to-video/ov_wan_helper.py
curl -fL -o taehv.py https://raw.githubusercontent.com/madebyollin/taehv/011dfc2112197741c540e0bdd5b7b67bcc930771/taehv.py
curl -fL -o taew2_1.safetensors https://github.com/madebyollin/taehv/raw/011dfc2112197741c540e0bdd5b7b67bcc930771/safetensors/taew2_1.safetensors
sha256sum ov_wan_helper.py taehv.py taew2_1.safetensors
```

**Kiểm tra:** 16 ký tự đầu của SHA256 khớp bảng ở trên. Khác thì dừng và báo người dùng.

## Bước 4. Tạo môi trường Python và cài thư viện

```bash
cd "$V"
uv venv --python 3.11 env
uv pip install --python env/Scripts/python.exe torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python env/Scripts/python.exe -r tao_video_lock.txt
```

Cài torch từ kho bản CPU **trước**, rồi mới cài theo `tao_video_lock.txt`. Lệnh thứ ba tải khoảng 2–3 GB; đặt thời gian chờ 10 phút hoặc chạy nền. Dòng cảnh báo `Multiple distributions found for package optimum` là bình thường.

**Kiểm tra:** `uv pip install` kết thúc không báo lỗi.

## Bước 5. Kiểm tra thư viện và GPU

```bash
cd "$V" && env/Scripts/python.exe -I -c "import sys; sys.path.insert(0, '.'); import torch, openvino as ov, ftfy, imageio_ffmpeg; from ov_wan_helper import OVWanPipeline; from taehv import TAEHV; print('torch', torch.__version__, '| openvino', ov.__version__, '| thiet bi', ov.Core().available_devices)"
```

Kết quả đúng (máy gốc):

```
torch 2.14.1+cpu | openvino 2026.2.0-21903-52ddc073857-releases/2026/2 | thiet bi ['CPU', 'GPU']
```

**Kiểm tra:** `torch` là `2.14.1+cpu`; danh sách thiết bị có `GPU`. Chỉ có `CPU` thì cập nhật driver đồ hoạ Intel, khởi động lại, kiểm tra lại. Vẫn không có thì có thể chạy `--dev cpu` nhưng rất chậm; nên chuyển sang bản Vulkan (`HUONG_DAN_CAI_TAO_VIDEO_AMD.md`, chạy được cả trên GPU Intel).

## Bước 6. Tải mô hình

```bash
cd "$V" && HF_HUB_DISABLE_XET=1 env/Scripts/python.exe -I -c "from huggingface_hub import snapshot_download; print(snapshot_download('liuming9157/Wan2.1-T2V-1.3B-Diffusers-ov-int4', revision='821bbdc4313add7f129deecbf5e56ef682df752d'))"
```

Tải khoảng 4,4 GB vào `C:/Users/<tên người dùng>/.cache/huggingface/hub`. Đặt thời gian chờ 10 phút hoặc chạy nền; bị ngắt thì chạy lại cùng lệnh. `HF_HUB_DISABLE_XET=1` là bắt buộc (kênh Xet từng trả lỗi 401). Không cần tài khoản Hugging Face. Không có mạng ổn định thì chép nguyên thư mục `%USERPROFILE%\.cache\huggingface\hub\models--liuming9157--Wan2.1-T2V-1.3B-Diffusers-ov-int4` từ máy gốc sang đúng chỗ đó trên máy mới.

**Kiểm tra:** đường dẫn in ra kết thúc bằng `snapshots\821bbdc4313add7f129deecbf5e56ef682df752d`, trong đó có `transformer.xml`, `transformer.bin` (0,77 GB), `text_encoder.xml`, `text_encoder.bin` (3,57 GB), `vae_decoder.xml`, `vae_decoder.bin`, `tokenizer/`, `scheduler/`.

Kho mô hình này do một cá nhân đăng (không phải Intel). Nếu kho bị xoá: chép từ máy gốc như trên, hoặc tự chuyển đổi bằng `convert_pipeline` trong `ov_wan_helper.py` (cần máy từ 32 GB RAM, xem notebook `wan2.1-text-to-video` của OpenVINO), hoặc dùng bản Vulkan.

## Bước 7. Tạo thử một clip nhỏ

Trước khi chạy: RAM trống nên từ 8 GB. Nhờ người dùng đóng Chrome, Docker Desktop, PowerPoint nếu thiếu. Không chạy hai tiến trình tạo video/ảnh cùng lúc.

```bash
cd "$V" && env/Scripts/python.exe -I tao_video.py --prompt "A small white church with a red roof on a green hill, clouds drifting slowly across the blue sky, gentle wind moving the grass, cinematic" --out "$V/thu/clip_thu.mp4" --w 512 --h 288 --frames 17 > "$V/thu_log.txt" 2>&1; tr '\r' '\n' < "$V/thu_log.txt" | grep -E "nap|OK|rror|Trace"
```

Lần đầu mất thêm khoảng 3–4 phút để biên dịch mô hình cho GPU (lưu ở `ov_cache/`, các lần sau nhanh). Kết quả đúng có dạng (máy gốc đo được tạo chuyển động 24 giây; số giây giải mã bằng TAEHV ở cỡ này chưa đo):

```
nap mo hinh (gpu): 213s
OK C:\...\thu\clip_thu.mp4  512x288  17 khung = 1.1s  tao chuyen dong 24s, giai ma ...s
```

**Kiểm tra:** có dòng `OK`, mã thoát 0. **Xem clip**: trích ba khung hình rồi mở ảnh ra xem:

```bash
FF=$(env/Scripts/python.exe -I -c "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())")
"$FF" -v error -y -i "$V/thu/clip_thu.mp4" -vf "select=eq(n\,0)+eq(n\,8)+eq(n\,16),tile=3x1" -frames:v 1 "$V/thu/xem.png"
```

Phải là nhà thờ trên đồi; ba khung khác nhau chút ít (có chuyển động). Đen, xám, nhiễu là lỗi (xem bảng lỗi).

## Bước 8. Đo cỡ mặc định

```bash
cd "$V" && env/Scripts/python.exe -I tao_video.py --prompt "A group of children in white shirts and blue scarves walking along a country road toward a small white church, trees swaying in the wind, warm morning light, storybook animation style" --out "$V/thu/clip_832.mp4" > "$V/thu_log2.txt" 2>&1
```

Mất khoảng 10 phút; chạy nền hoặc đặt thời gian chờ đủ dài. Ghi lại các số `tao chuyen dong` và `giai ma` để điền vào bảng thời gian cuối file.

## Bước 9. Báo cáo cho người dùng

Báo ngắn gọn: `<ROOT>`, thiết bị (GPU), thời gian hai clip thử, đường dẫn clip, và cách dùng (mục dưới). Xoá `<ROOT>/tao_video/thu` nếu người dùng không cần. Nếu agent có bộ nhớ lâu dài (CLAUDE.md hay thư mục memory), ghi một dòng trỏ tới file này.

## Cách dùng sau khi cài

Một clip:

```bash
<ROOT>/tao_video/env/Scripts/python.exe -I <ROOT>/tao_video/tao_video.py --prompt "..." --out D:/duong/dan/clip.mp4 [--w 832 --h 480] [--frames 33] [--seed 7]
```

Nhiều clip trong một lần chạy (mô hình chỉ nạp một lần, nên dùng khi từ 2 clip trở lên):

```bash
<ROOT>/tao_video/env/Scripts/python.exe -I <ROOT>/tao_video/tao_video.py --jobs D:/duong/dan/viec.json
```

`viec.json` là danh sách; mỗi phần tử có `prompt` và `out`, tuỳ chọn `w`, `h`, `frames`, `seed`. Clip đã có thì bỏ qua (chạy lại là làm tiếp), thêm `--overwrite` để tạo lại. Script làm theo ba giai đoạn cho cả danh sách (mã hoá lời mô tả, tạo chuyển động, giải mã), nên **các clip chỉ được ghi ra ở cuối**; bị ngắt giữa chừng thì mất cả lượt.

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--prompt` | | Lời mô tả, **viết bằng tiếng Anh** |
| `--out` | | File ra `.mp4`; thư mục chưa có sẽ được tạo |
| `--w`, `--h` | 832, 480 | Cỡ khung hình; tự làm tròn lên bội số của 16 rồi cắt lại. Dùng số chẵn |
| `--frames` | 33 | Số khung hình, dạng 4k+1 (17, 33, 49, 81). 81 khung = 5 giây là giới hạn mô hình được huấn luyện |
| `--fps` | 16 | Wan2.1 được huấn luyện ở 16 khung/giây |
| `--seed` | 7 | Đổi seed để có phương án khác |
| `--steps` | 4 | Giữ 4 (mô hình đã gộp LoRA CausVid chưng cất cho 4 bước) |
| `--dev` | `gpu` | `cpu` chậm hơn nhiều |
| `--vae-day-du` | tắt | Giải mã bằng VAE gốc của Wan thay cho TAEHV: chậm hơn khoảng 15–20 lần, hình gần như không khác. Chỉ dùng khi TAEHV cho hình lỗi |
| `--overwrite` | tắt | Ghi đè clip đã có |

Kết quả in ra: mỗi clip một dòng `OK <đường dẫn> <cỡ> <số khung> = <giây>s  tao chuyen dong <giây>s, giai ma <giây>s`. Hết việc thì in `khong con clip nao phai tao`.

Viết lời mô tả: tiếng Anh, câu đầy đủ, nêu rõ chủ thể, **hành động bằng động từ chuyển động** (walking, swaying, drifting, turning, waving), bối cảnh, ánh sáng, phong cách (`storybook animation style`, `cinematic`, `realistic`). Clip chỉ 1–5 giây nên mỗi clip một hành động đơn giản; muốn dài thì tạo nhiều clip rồi nối bằng ffmpeg. Mô hình 1,3B hay vẽ sai tay, mặt khi người ở xa, tự thêm người, và không viết được chữ: **luôn xem clip trước khi dùng**.

## Thời gian đo trên máy gốc (i7-1260P, Iris Xe, 16 GB, 4 bước)

| Cỡ | Tạo chuyển động | Giải mã (TAEHV) | Ghi chú |
|---|---|---|---|
| 512×288, 17 khung (1 giây) | 24 giây | chưa đo | |
| 512×288, 33 khung (2 giây) | chưa đo | 25 giây | |
| 512×288, 81 khung (5 giây) | 221 giây | 31 giây | Đo 15/10/2026; cả lượt chạy (gồm nạp mô hình) 4 phút 50 giây. RAM đủ |
| 832×480, 33 khung (2 giây) | 360–530 giây | 34–65 giây | Dao động theo nhiệt độ máy và RAM trống |

Nạp mô hình 15–40 giây mỗi lần chạy (lần đầu tiên khoảng 3,5 phút để biên dịch). Giải mã bằng `--vae-day-du`: khoảng 500 giây cho 512×288 33 khung, khoảng 950–1065 giây cho 832×480 33 khung.

Chọn cỡ: thử lời mô tả ở 512×288 cho nhanh, rồi chạy lại cùng seed ở 832×480.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| `uv` hoặc `git` không nhận lệnh | PATH chưa cập nhật. Mở cửa sổ dòng lệnh mới |
| Đường dẫn dính liền, kiểu `C:Usersx` | Dùng `\` trong Git Bash. Đổi sang `/` |
| Lỗi 401 khi tải mô hình | Thiếu `HF_HUB_DISABLE_XET=1`. Script tự đặt; lệnh tải ở bước 6 cũng đã đặt |
| `ModuleNotFoundError: ov_wan_helper` hoặc `taehv` | Thiếu file cạnh `tao_video.py` (bước 2–3) |
| `ModuleNotFoundError: ftfy` hoặc `imageio_ffmpeg` | Cài chưa đúng `tao_video_lock.txt`; chạy lại bước 4 |
| Không thấy `GPU` trong danh sách thiết bị | Cập nhật driver đồ hoạ Intel, khởi động lại |
| Máy đơ, RAM trống xuống dưới 1 GB, tiến trình bị ngắt | Thiếu RAM. Đóng bớt ứng dụng, giảm cỡ clip. Bị ngắt thì báo người dùng, đừng tự chạy lại liên tục |
| Một bước chạy lâu bất thường (hàng chục phút đến hàng giờ) | Máy đã ngủ (Modern Standby) giữa chừng; xem Event Viewer → System, Kernel-Power 506/507. Tiến trình chỉ bị treo, không chết: máy thức dậy thì nó chạy tiếp, nên đừng chạy lại song song (lần chạy mới sẽ không ghi được file nhật ký). `tao_video.py` tự giữ máy thức khi để yên, nhưng gập nắp vẫn ngủ. Dặn người dùng không gập nắp và cắm sạc |
| Clip chỉ có 17 khung dù xin nhiều hơn | Đang dùng bộ giải mã OpenVINO trong kho mô hình (bị cố định 17 khung). `tao_video.py` bản hiện tại không dùng nó; kiểm tra đã chép đúng script |
| Clip đen, xám hoặc nhiễu | Thử `--vae-day-du`; vẫn lỗi thì thử `--dev cpu` với cỡ nhỏ. CPU ra đúng thì lỗi ở driver GPU: cập nhật driver rồi xoá `ov_cache/` |
