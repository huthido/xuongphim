# Hướng dẫn cài công cụ tạo video clip từ lời mô tả cho máy AMD (Wan2.1 + stable-diffusion.cpp, Vulkan)

Dành cho agent (Claude Code hoặc tương tự) được giao cài công cụ tạo video ngắn từ lời mô tả lên một máy Windows dùng **CPU AMD Ryzen và GPU AMD Radeon** (card rời hoặc card tích hợp "AMD Radeon Graphics"). Cách này cũng chạy được trên GPU Intel hoặc NVIDIA. Máy có GPU Intel thì nên dùng bản OpenVINO (`HUONG_DAN_CAI_TAO_VIDEO.md`) vì nhanh hơn.

Làm lần lượt từng bước. Mỗi bước có phần **Kiểm tra**; chưa đạt thì dừng lại sửa, đừng làm tiếp.

## Tóm tắt

| | |
|---|---|
| Kết quả | Lệnh `powershell -ExecutionPolicy Bypass -File <ROOT>/tao_video_amd/tao_video_amd.ps1 -Prompt "..." -Out clip.mp4` tạo được clip .mp4 (H.264) |
| Mô hình | Wan2.1-T2V-1.3B (Apache 2.0) + LoRA chưng cất CausVid để chỉ cần 4 bước + bộ giải mã nhanh TAEHV `taew2_1` (MIT). Giống mô hình của bản Intel, khác định dạng file |
| Chương trình | stable-diffusion.cpp bản dựng sẵn `master-964-1d0a58a`, gói `win-vulkan-x64`. Không cần Python |
| Chạy trên | GPU qua Vulkan (driver AMD Adrenalin có sẵn Vulkan) |
| Clip ra | Mặc định 832×480, 33 khung hình, 16 khung/giây = khoảng 2 giây. Không có tiếng |
| Dung lượng tải | Khoảng 7,4 GB |

**Bổ sung 16/10/2026:**
- **Wan2.2 TI2V-5B:** tạo video **từ ảnh** (giữ đúng mặt nhân vật), đẹp hơn hẳn Wan2.1 1.3B.
- **`tao_video_sd.py`:** script Python thay `tao_video_amd.ps1`, chạy được trên **Windows, Linux, macOS**.
- **Giao diện Xưởng phim:** `<ROOT>/xuong_phim`, gọi script trên.

Xem **Phần B** cuối file. Phần A (các bước 0–8) vẫn đúng cho Wan2.1.

**Mức đã kiểm chứng (14/10/2026):** toàn bộ các bước dưới đây đã chạy thật trên máy gốc, nhưng máy gốc dùng **GPU Intel Iris Xe** qua Vulkan, **chưa thử trên GPU AMD**. Lệnh, file mô hình và tham số đã đúng; điểm duy nhất chưa biết là driver AMD và tốc độ. Vì vậy bước 6–7 là bắt buộc, và phải báo người dùng số đo thật.

## Hai file mang từ máy gốc sang

Lấy từ `<ROOT>\tao_video_amd\` trên máy gốc:

| File | Vai trò |
|---|---|
| `tao_video_amd.ps1` | Script tạo clip (gọi stable-diffusion.cpp rồi ffmpeg) |
| `HUONG_DAN_CAI_TAO_VIDEO_AMD.md` | File này |

Thiếu `tao_video_amd.ps1` thì dừng và xin người dùng; đừng tự viết lại.

## Yêu cầu máy

| | Tối thiểu | Ghi chú |
|---|---|---|
| Hệ điều hành | Windows 10/11 64-bit | |
| RAM | 16 GB | Card tích hợp dùng chung RAM. Mô hình chiếm khoảng 7 GB khi chạy |
| Ổ đĩa trống | 15 GB | Mô hình 7,3 GB, chương trình 30 MB, ffmpeg, file tạm |
| GPU | AMD Radeon hỗ trợ Vulkan | Gần như mọi Radeon từ 2016 trở đi: card tích hợp Vega, 610M, 660M/680M, 760M/780M, 880M/890M; card rời RX 400 trở lên |
| Driver | AMD Software: Adrenalin Edition bản mới | Driver cũ hay driver mặc định của Windows có thể thiếu Vulkan |
| Mạng | Cần khi cài | Sau khi cài xong thì chạy không cần mạng |

## Quy ước

- `<ROOT>` là thư mục cài. Mặc định `C:/Users/<tên người dùng>/AI`. Người dùng chỉ định chỗ khác thì dùng chỗ đó. **Không dùng đường dẫn có dấu cách hay dấu tiếng Việt.**
- Lệnh viết cho **Git Bash** (đường dẫn dùng `/`); lệnh có ghi PowerShell thì chạy trong PowerShell. Máy không có Git Bash thì chạy mọi lệnh `curl` trong PowerShell bằng `curl.exe` (có sẵn trong Windows 10/11).
- Biến như `A=...` không giữ được giữa các lần gọi lệnh của agent; mỗi lệnh hãy đặt lại hoặc viết thẳng đường dẫn.
- Bố cục phải đúng như sau, vì script tìm `sd/` và `models/` cạnh nó:

```
<ROOT>/tao_video_amd/
  tao_video_amd.ps1
  HUONG_DAN_CAI_TAO_VIDEO_AMD.md
  sd/                 (bước 3: sd-cli.exe và các .dll)
  models/             (bước 4)
    wan2.1_t2v_1.3B_fp16.safetensors
    wan_2.1_vae.safetensors        (chỉ dùng khi chạy -VaeDayDu)
    taew2_1.safetensors
    umt5-xxl-encoder-Q5_K_M.gguf
    loras/
      Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors
```

## Bước 0. Kiểm tra máy và hỏi người dùng

Chạy trong PowerShell:

```powershell
(Get-CimInstance Win32_Processor).Name
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate
"RAM tong: {0} GB" -f [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)
"RAM trong: {0} GB" -f [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)
Get-PSDrive C | Select-Object @{n='TrongGB';e={[math]::Round($_.Free/1GB)}}
```

**Kiểm tra:** RAM tổng từ 16 GB, ổ trống từ 15 GB, có dòng GPU AMD Radeon. Báo người dùng cấu hình máy và xin xác nhận `<ROOT>` trước khi cài. Nếu ngày driver GPU cũ hơn khoảng một năm, đề nghị người dùng cập nhật AMD Adrenalin (https://www.amd.com/en/support/download/drivers.html) trước.

## Bước 1. Cài ffmpeg (và Git nếu chưa có)

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
```

Git chỉ để có Git Bash; không bắt buộc. Cài xong phải **mở cửa sổ dòng lệnh mới** (hoặc khởi động lại phiên agent) để PATH cập nhật. Script vẫn tự tìm được ffmpeg trong thư mục WinGet nếu PATH chưa cập nhật.

**Kiểm tra:** `ffmpeg -version` in ra phiên bản (máy gốc dùng ffmpeg 9.0.2).

## Bước 2. Đặt hai file vào `<ROOT>/tao_video_amd`

```bash
A=C:/Users/<tên người dùng>/AI/tao_video_amd      # sửa cho đúng
mkdir -p "$A/sd" "$A/models/loras"
# chép tao_video_amd.ps1 và HUONG_DAN_CAI_TAO_VIDEO_AMD.md vào "$A"
ls "$A"
```

**Kiểm tra:** `ls` thấy `tao_video_amd.ps1`, `HUONG_DAN_CAI_TAO_VIDEO_AMD.md`, `sd/`, `models/`.

## Bước 3. Tải stable-diffusion.cpp bản Vulkan

Dùng đúng bản đã thử, không lấy bản mới nhất (dự án ra bản mới hằng ngày, tham số có thể đổi):

```bash
cd "$A"
curl -L -o sd.zip https://github.com/leejet/stable-diffusion.cpp/releases/download/master-964-1d0a58a/sd-master-1d0a58a-bin-win-vulkan-x64.zip
sha256sum sd.zip
unzip -o sd.zip -d sd && rm sd.zip
sd/sd-cli.exe --list-devices
```

PowerShell thay cho `sha256sum` và `unzip`: `Get-FileHash sd.zip` và `Expand-Archive sd.zip -DestinationPath sd -Force`.

**Kiểm tra:**
- SHA256 phải là `74211cb5c382aec2aeb086b64f2fdf525efec5faec4200a2d3257bc2328954ab`. Khác thì xoá file, tải lại; vẫn khác thì dừng và báo người dùng.
- `--list-devices` phải có một dòng `Vulkan0	AMD Radeon ...`. Máy gốc in ra `Vulkan0	Intel(R) Iris(R) Xe Graphics` và `CPU	...`. Chỉ thấy `CPU` thì xem bảng lỗi (driver).

## Bước 4. Tải mô hình

Mỗi file tải từ Hugging Face theo đúng bản (revision) đã thử. `-C -` cho phép chạy lại cùng lệnh để tải tiếp khi bị ngắt. Lệnh lớn nhất mất vài phút đến vài chục phút tuỳ mạng; đặt thời gian chờ 10 phút hoặc chạy nền.

```bash
cd "$A/models"
H=https://huggingface.co
curl -L -C - -o wan2.1_t2v_1.3B_fp16.safetensors $H/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/123acf1cc74bccbb9bfff8ac1ee72edc08c2341d/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors
curl -L -C - -o wan_2.1_vae.safetensors $H/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/123acf1cc74bccbb9bfff8ac1ee72edc08c2341d/split_files/vae/wan_2.1_vae.safetensors
curl -L -C - -o umt5-xxl-encoder-Q5_K_M.gguf $H/city96/umt5-xxl-encoder-gguf/resolve/b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7/umt5-xxl-encoder-Q5_K_M.gguf
curl -L -C - -o taew2_1.safetensors https://github.com/madebyollin/taehv/raw/011dfc2112197741c540e0bdd5b7b67bcc930771/safetensors/taew2_1.safetensors
curl -L -C - -o loras/Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors $H/Kijai/WanVideo_comfy/resolve/8260d429d19fd7a72304cad059160b95d843913f/Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors
ls -l . loras
```

Không cần tài khoản hay khoá Hugging Face. Không có mạng ổn định thì chép nguyên thư mục `<ROOT>\tao_video_amd\models` từ máy gốc sang.

**Kiểm tra:** kích thước phải khớp **đúng từng byte**:

| File | Byte |
|---|---|
| `wan2.1_t2v_1.3B_fp16.safetensors` | 2838303560 |
| `wan_2.1_vae.safetensors` | 253815318 |
| `taew2_1.safetensors` | 22642902 |
| `umt5-xxl-encoder-Q5_K_M.gguf` | 4145878880 |
| `loras/Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors` | 91233416 |

File nhỏ hơn thì chạy lại đúng lệnh `curl` của file đó. File chỉ vài trăm byte thường là trang báo lỗi; xoá đi rồi tải lại.

## Bước 5. Chuẩn bị chạy

Đóng bớt Chrome, Docker Desktop, PowerPoint; RAM trống nên từ 8 GB. Không chạy hai tiến trình tạo video cùng lúc. Không chạy song song với công cụ tạo ảnh.

## Bước 6. Tạo thử một clip nhỏ

PowerShell (hoặc Git Bash với `powershell -NoProfile -ExecutionPolicy Bypass -File ...`):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/<tên người dùng>/AI/tao_video_amd/tao_video_amd.ps1 -Prompt "A small white church with a red roof on a green hill, clouds drifting slowly across the blue sky, gentle wind moving the grass, cinematic" -Out C:/Users/<tên người dùng>/AI/tao_video_amd/thu/clip_thu.mp4 -W 512 -H 288 -Frames 17 > C:/Users/<tên người dùng>/AI/tao_video_amd/thu_log.txt 2>&1
```

sd-cli in rất nhiều dòng; luôn ghi ra file log như trên rồi lọc:

```bash
grep -E "Vulkan0|total params|LoRA tensors|sampling completed|decode_first_stage completed|OK |rror|loi" "$A/thu_log.txt"
```

Kết quả trên máy gốc (Iris Xe, để so). Lần đo này dùng VAE gốc (`-VaeDayDu`); mặc định hiện nay là TAEHV nên dòng `total params` ghi `vae 21.59MB` và bước giải mã nhanh hơn nhiều:

```
[I] total params memory size = 6898.76MB (VRAM 6898.76MB, RAM 0.00MB): text_encoders 3947.75MB(VRAM), diffusion_model 2708.92MB(VRAM), vae 242.10MB(VRAM) ...
[I] sampling completed, taking 141.82s
[I] decode_first_stage completed, taking 258.08s
[I] (1099 / 1099) LoRA tensors have been applied, lora_file_path = ...Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32.safetensors
OK C:\...\thu\clip_thu.mp4  512x288  17 khung = 1.1s  432s
```

**Kiểm tra:**
- Có dòng `OK`, và dòng `(1099 / 1099) LoRA tensors have been applied`. Thiếu dòng LoRA thì clip sẽ nhoè vì chỉ chạy 4 bước: kiểm tra lại tên và chỗ đặt file LoRA.
- `total params memory size` ghi `VRAM` là đang chạy trên GPU. Ghi phần lớn là `RAM` là GPU không đủ bộ nhớ, chương trình tự đẩy sang RAM (chậm hơn; xem bảng lỗi).
- **Xem clip**: trích ba khung hình rồi mở ảnh ra xem:

```bash
ffmpeg -v error -y -i "$A/thu/clip_thu.mp4" -vf "select=eq(n\,0)+eq(n\,8)+eq(n\,16),tile=3x1" -frames:v 1 "$A/thu/xem.png"
```

Phải là nhà thờ trên đồi, mây ở ba khung hơi khác vị trí (có chuyển động). Ảnh đen, xám, nhiễu, sọc là lỗi (xem bảng lỗi).

## Bước 7. Đo cỡ mặc định

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <ROOT>/tao_video_amd/tao_video_amd.ps1 -Prompt "A group of children in white shirts and blue scarves walking along a country road toward a small white church, trees swaying in the wind, warm morning light, storybook animation style" -Out <ROOT>/tao_video_amd/thu/clip_832.mp4 > <ROOT>/tao_video_amd/thu_log2.txt 2>&1
```

Ghi lại thời gian `sampling completed`, `decode_first_stage completed` và tổng ở dòng `OK`. Lệnh này có thể mất 10–40 phút; chạy nền hoặc đặt thời gian chờ đủ dài. Nếu quá chậm so với nhu cầu người dùng, đề nghị dùng cỡ 512×288 hoặc 640×368.

## Bước 8. Báo cáo cho người dùng

Báo ngắn gọn: `<ROOT>`, tên GPU, chạy trên GPU hay bị đẩy sang RAM/CPU, thời gian clip thử và clip cỡ mặc định, đường dẫn hai clip, và lệnh dùng (mục dưới). Ghi số đo vào bảng "Thời gian đo" cuối file này. Nếu agent có bộ nhớ lâu dài (CLAUDE.md hay thư mục memory), ghi một dòng trỏ tới file này.

## Cách dùng sau khi cài

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <ROOT>/tao_video_amd/tao_video_amd.ps1 -Prompt "..." -Out D:/duong/dan/clip.mp4 [-W 832 -H 480] [-Frames 33] [-Seed 7]
powershell -NoProfile -ExecutionPolicy Bypass -File <ROOT>/tao_video_amd/tao_video_amd.ps1 -Jobs D:/duong/dan/viec.json
```

`viec.json` là danh sách; mỗi phần tử có `prompt` và `out`, tuỳ chọn `w`, `h`, `frames`, `seed`. Clip đã có thì bỏ qua (chạy lại là làm tiếp), thêm `-Overwrite` để tạo lại. Mỗi clip nạp lại mô hình, mất thêm vài giây.

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `-Prompt` | | Lời mô tả, **viết bằng tiếng Anh**. Không dùng dấu ngoặc kép `"` bên trong (script đổi thành `'`) |
| `-Out` | | File ra `.mp4`; thư mục chưa có sẽ được tạo |
| `-W`, `-H` | 832, 480 | Cỡ khung hình. Script làm tròn lên bội số của 16 rồi cắt lại. Dùng số chẵn |
| `-Frames` | 33 | Số khung hình; mô hình dùng dạng 4k+1 (17, 33, 49, 81). 81 khung = 5 giây là giới hạn mô hình được huấn luyện |
| `-Fps` | 16 | Wan2.1 được huấn luyện ở 16 khung/giây |
| `-Seed` | 7 | Đổi seed để có phương án khác |
| `-Steps` | 4 | Giữ 4 (LoRA CausVid chưng cất cho 4 bước) |
| `-VaeDayDu` | tắt | Giải mã bằng VAE gốc của Wan thay cho TAEHV. Chi tiết mịn hơn chút nhưng chậm hơn nhiều lần; chỉ dùng khi TAEHV cho hình lỗi |
| `-Cpu` | tắt | Chạy bằng CPU. Rất chậm; chỉ dùng để thử khi GPU lỗi |
| `-Extra` | | Tham số thêm cho sd-cli, ví dụ `-Extra "--offload-to-cpu"` |
| `-Overwrite` | tắt | Ghi đè clip đã có |

Viết lời mô tả: tiếng Anh, câu đầy đủ, nêu rõ chủ thể, hành động (**động từ chuyển động**: walking, swaying, drifting, turning), bối cảnh, ánh sáng, phong cách. Clip chỉ dài 1–5 giây, nên mỗi clip một hành động đơn giản. Muốn clip dài thì tạo nhiều clip rồi nối bằng ffmpeg. Mô hình 1,3B hay vẽ sai tay, mặt khi người ở xa, và không viết được chữ: luôn xem clip trước khi dùng.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| `--list-devices` không có `Vulkan0` | Driver GPU thiếu Vulkan. Cài lại AMD Adrenalin bản mới, khởi động lại máy |
| `ErrorDeviceLost`, `out of device memory`, hoặc `total params` ghi phần lớn là `RAM` | Card tích hợp được cấp ít bộ nhớ riêng. Thử `-Extra "--offload-to-cpu"`. Vẫn lỗi thì nhờ người dùng tăng **UMA Frame Buffer Size** trong BIOS (ví dụ 4–8 GB) hoặc đặt "Variable Graphics Memory" trong AMD Adrenalin, khởi động lại. Thử cỡ nhỏ hơn (`-W 512 -H 288 -Frames 17`) |
| Clip đen, xám, sọc hoặc toàn nhiễu | Thử lại với `-Cpu` cùng lệnh và cỡ nhỏ. CPU ra clip đúng thì lỗi nằm ở driver Vulkan: cập nhật driver |
| Clip nhoè, mờ, như sương | LoRA CausVid không được áp dụng (log thiếu dòng `LoRA tensors have been applied`). Kiểm tra file trong `models/loras/` |
| `sd-cli loi` ngay từ đầu, log báo không mở được file | Sai tên hoặc chỗ đặt file mô hình. So với sơ đồ bố cục và bảng kích thước ở bước 4 |
| `khong tim thay ffmpeg` | Chưa cài ffmpeg (bước 1) hoặc chưa mở lại cửa sổ dòng lệnh |
| PowerShell báo không cho chạy script | Luôn gọi qua `powershell -ExecutionPolicy Bypass -File ...` như trên |
| Máy đơ, tiến trình bị ngắt | Thiếu RAM. Đóng bớt ứng dụng, giảm cỡ clip. Bị ngắt thì báo người dùng, đừng tự chạy lại liên tục |

## Thời gian đo

| Máy | Cỡ | Tạo chuyển động | Giải mã | Tổng |
|---|---|---|---|---|
| Máy gốc: i7-1260P, Intel Iris Xe (Vulkan), 16 GB | 512×288, 17 khung | 142 giây | 258 giây (VAE gốc) | 432 giây |
| Máy gốc, cỡ mặc định 832×480, 33 khung, TAEHV | | chưa đo được: tiến trình bị Claude Code ngắt vì máy gần hết RAM | | |
| Máy AMD (agent điền sau bước 6–7) | | | | |

Không có bộ đệm biên dịch: lần chạy đầu và các lần sau gần như nhau.

---

# Phần B. Wan2.2 TI2V-5B (video từ ảnh) và `tao_video_sd.py` cho mọi hệ điều hành

Phần B dùng chung `sd/` và `models/umt5-xxl-encoder-Q5_K_M.gguf` của phần A. Muốn chỉ dùng Wan2.2 thì làm bước 1–3 của phần A, tải riêng `umt5-xxl-encoder-Q5_K_M.gguf` ở bước 4, rồi làm tiếp phần này.

| | |
|---|---|
| Kết quả | `python <ROOT>/tao_video_amd/tao_video_sd.py --anh nhan_vat.png --prompt "..." --out clip.mp4` tạo clip .mp4 cho nhân vật trong ảnh chuyển động |
| Mô hình | Wan2.2-TI2V-5B bản Turbo (chưng cất, 4 bước), lượng tử Q4_K_M + bộ giải mã nhanh TAEHV `taew2_2` |
| Clip ra | Mặc định 640×352, 121 khung, 24 khung/giây = 5 giây. Không có tiếng |
| Cần thêm | Python 3.9+ (chỉ thư viện chuẩn) và ffmpeg. Tải thêm khoảng 4,9 GB |

## B1. Đặt script

Chép `tao_video_sd.py` vào `<ROOT>/tao_video_amd/` (cạnh `sd/` và `models/`). File gốc dài 9.092 byte.

## B2. sd-cli cho Linux và macOS (Windows đã có từ bước 3)

Cùng bản `master-964-1d0a58a`. Chọn gói theo máy; SHA256 lấy từ trang phát hành GitHub:

| Máy | Gói | SHA256 |
|---|---|---|
| Linux x86_64, GPU AMD/Intel/NVIDIA (Vulkan) | `sd-master-1d0a58a-bin-Linux-Ubuntu-24.04-x86_64-vulkan.zip` | `bade142929edfa7aad56aba46376e55142d14390262b904f4a2deb3a03ceb21d` |
| Linux x86_64, GPU AMD có ROCm 10.1 | `sd-master-1d0a58a-bin-Linux-Ubuntu-24.04-x86_64-rocm-10.1.0.zip` | `a00fcd3233e8acfc8f5aadb0a1ab4e137a37d05dc61e2a37ddf94d7232b121ca` |
| macOS Apple Silicon (Metal) | `sd-master-1d0a58a-bin-Darwin-macOS-26.6.2-arm64.zip` | `45001839e925f98ecd18ef5251725f74cff874eeac4599f1136acba65b26911e` |

```bash
cd <ROOT>/tao_video_amd
curl -L -o sd.zip https://github.com/leejet/stable-diffusion.cpp/releases/download/master-964-1d0a58a/<tên gói>
sha256sum sd.zip            # macOS: shasum -a 256 sd.zip
unzip -o sd.zip -d sd && rm sd.zip
find sd -name 'sd-cli*'     # nếu sd-cli nằm trong thư mục con, chuyển nó (và các thư viện đi kèm) lên sd/
chmod +x sd/sd-cli
xattr -dr com.apple.quarantine sd    # chỉ macOS
sd/sd-cli --list-devices
```

Linux cần driver Vulkan (Ubuntu: `sudo apt install mesa-vulkan-drivers vulkan-tools`; kiểm bằng `vulkaninfo --summary`).

**Kiểm tra:** `--list-devices` phải có dòng GPU: `Vulkan0 ...` trên Linux, hoặc `Metal`/`MTL0` trên macOS. sd-cli để chỗ khác thì đặt biến `SD_CLI=/duong/dan/sd-cli`.

Linux và macOS **chưa chạy thử trên máy thật**. Phải làm bước B4 rồi báo số đo.

## B3. Tải mô hình Wan2.2

```bash
cd <ROOT>/tao_video_amd/models && mkdir -p wan22 && cd wan22
H=https://huggingface.co
curl -L -C - -o Wan2_2-TI2V-5B-Turbo-Q4_K_M.gguf $H/hum-ma/Wan2.2-TI2V-5B-Turbo-GGUF/resolve/9873ba175b4b204a81f4a43c9644e6c385ee4459/Wan2_2-TI2V-5B-Turbo-Q4_K_M.gguf
curl -L -C - -o taew2_2.safetensors https://github.com/madebyollin/taehv/raw/011dfc2112197741c540e0bdd5b7b67bcc930771/safetensors/taew2_2.safetensors
# tuỳ chọn, chỉ cho --vae-day-du (1,4 GB):
curl -L -C - -o wan2.2_vae.safetensors $H/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/ee6f4a40737a995bf5818954cfce6d59443b0f04/split_files/vae/wan2.2_vae.safetensors
sha256sum *
```

**Kiểm tra:**

| File | Byte | SHA256 |
|---|---|---|
| `Wan2_2-TI2V-5B-Turbo-Q4_K_M.gguf` | 3437927136 | `13b3bee8fcafd9f9a3778ed1a0ca973f4a7d152094ea305f8384b0abd7e1ad51` |
| `taew2_2.safetensors` | 22848048 | `b84609b2a133d48434bd9636bfcb44bf05168dc436e2d3cecf26256faa1f5325` |
| `wan2.2_vae.safetensors` (tuỳ chọn) | 1409400960 | `e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156` |

## B4. Tạo thử

Cần một ảnh rõ mặt (ví dụ ảnh chân dung bất kỳ, hoặc ảnh tạo bằng công cụ tạo ảnh). Ảnh được tự động thu nhỏ và cắt giữa cho vừa khung.

```bash
python <ROOT>/tao_video_amd/tao_video_sd.py --anh anh.png --frames 49 \
  --prompt "The person smiles warmly and nods slowly, blinking naturally. Static camera, soft natural light, photorealistic real footage." \
  --out <ROOT>/tao_video_amd/thu/thu_22.mp4 > <ROOT>/tao_video_amd/thu_log22.txt 2>&1
grep -E "^==|total params|sampling completed|decode_first_stage completed|^OK|rror|loi" <ROOT>/tao_video_amd/thu_log22.txt
```

Windows dùng `python` của bất kỳ venv nào, ví dụ `<ROOT>/long_tieng/env/Scripts/python.exe`. Linux và macOS dùng `python3`.

**Kiểm tra:** có dòng `OK`, `total params` ghi VRAM, và ba khung trích ra (như bước 6) giống người trong ảnh.

## Cách dùng `tao_video_sd.py`

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--mo-hinh` | `wan22` | `wan22`: Wan2.2 5B. `wan21`: Wan2.1 1.3B + CausVid (như `tao_video_amd.ps1`) |
| `--anh` | | Ảnh khung đầu (chỉ wan22). Bỏ trống thì tạo từ lời mô tả |
| `--prompt`, `--out` | | Lời mô tả tiếng Anh; file .mp4 ra |
| `--jobs` | | JSON danh sách `{"prompt","out","anh"?,"w"?,"h"?,"frames"?,"seed"?}`; clip đã có thì bỏ qua |
| `--w`, `--h` | 640×352 (wan22), 832×480 (wan21) | Làm tròn lên bội số 32 (wan22) hoặc 16 (wan21) rồi cắt lại |
| `--frames` | 121 (wan22), 33 (wan21) | Làm tròn về dạng 4k+1. wan22: 49 = 2 giây, 121 = 5 giây |
| `--fps` | 24 (wan22), 16 (wan21) | |
| `--seed`, `--steps` | 7, 4 | Giữ 4 bước |
| `--vae-day-du` | tắt | VAE gốc thay TAEHV. **Với wan22 trên GPU dùng chung RAM (Iris Xe) làm GPU bị ngắt (`device lost`) sau 75 phút; đừng dùng** |
| `--cpu`, `--extra "..."`, `--overwrite` | | Như `-Cpu`, `-Extra`, `-Overwrite` của phần A |

Script giữ máy không tự ngủ trong lúc chạy:
- Windows: `SetThreadExecutionState`.
- macOS: `caffeinate`.
- Linux: `systemd-inhibit`.

Khi khởi động, script xoá các thư mục tạm `tao_video_sd_*` cũ hơn 6 giờ (sót lại khi bị huỷ giữa chừng).

## Bài học khi thử Wan2.2 trên máy gốc (16 GB RAM, Iris Xe)

- **Cỡ 640×352 vừa máy 16 GB.** Mô hình và umT5 chiếm khoảng 7,2 GB bộ nhớ GPU dùng chung. 832×480×121 khung xin khoảng 19 GB nên máy swap liên tục: cần GPU rời hoặc từ 32 GB RAM.
- **Phải dùng TAEHV `taew2_2`.** VAE gốc của Wan2.2 làm driver ngắt GPU. Đổi sang TAE còn bớt 1,3 GB RAM, nên phần chuyển động cũng nhanh hơn khoảng 5 lần.
- **Clip đẹp và thật**, giữ đúng mặt, quần áo và bối cảnh trong ảnh, làm đúng chuỗi động tác trong lời mô tả.
- **Hạn chế:** thỉnh thoảng có vệt màu (cam, hồng, tím) lóe lên 1–2 khung ở mép người hoặc nền. Đổi seed để thử lại.
- Mỗi clip một người, cận cảnh. Hai người khác tuổi trong cùng khung bị làm giống nhau (bài học từ Wan2.1, chưa thử lại với 5B).

## Thời gian đo, Wan2.2 5B (TAEHV)

| Máy | Cỡ | Tạo chuyển động | Giải mã | Tổng |
|---|---|---|---|---|
| Máy gốc: i7-1260P, Iris Xe (Vulkan), 16 GB, Windows 11 | 640×352, 49 khung (2 giây), từ ảnh | 119 giây | 4 giây | 140 giây |
| Máy gốc | 640×352, 121 khung (5 giây), từ ảnh | 491 giây | 32 giây | khoảng 10 phút |
| Máy gốc | 832×480, 121 khung | không chạy được: thiếu RAM | | |
| Linux / macOS / máy AMD (agent điền sau B4) | | | | |
