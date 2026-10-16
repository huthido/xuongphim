# Xưởng phim

Làm phim ngắn bằng AI **ngay trên máy của bạn**: tạo nhân vật, cho nhân vật chuyển động, lồng tiếng tiếng Việt, ghép phim. Không cần tài khoản, không gửi tệp lên máy chủ nào. Chạy trên Windows, macOS, Linux.

- **Video từ ảnh:** Wan2.2 TI2V-5B Turbo, chạy qua [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) trên GPU AMD, Intel, NVIDIA (Vulkan) hoặc Apple (Metal). Clip giữ đúng mặt nhân vật trong ảnh.
- **Lồng tiếng:** VieNeu-TTS, chạy trên CPU, có 25 giọng và chỉnh được cao độ.
- **Ghép phim:** nối clip, đặt lời thoại vào từng cảnh, thêm nhạc nền (ffmpeg).
- **Giao diện web và PWA:** cài thành ứng dụng, có hàng đợi chạy mỗi lần một việc, chờ đủ RAM rồi mới chạy.
- **Tự chọn mô hình hợp với máy:** kiểm tra CPU, RAM, GPU rồi đề xuất mô hình và kích thước cho chất lượng tốt nhất; tải và kiểm SHA256 tự động.
- **MCP:** gắn agent (Claude Code, Claude Desktop, Cursor…) để agent tự làm phim và tự xem khung hình kết quả.

## Cài nhanh

Cần **Python 3.9+** và **ffmpeg**.

```bash
git clone https://github.com/huthido/xuongphim
cd xuongphim
python xuong_phim/cai_dat.py kiem_may     # xem cấu hình máy và mô hình đề xuất
python xuong_phim/cai_dat.py de_xuat      # tải mô hình đề xuất (vài GB) + dựng lồng tiếng
```

Mở Xưởng phim:
- **Windows:** bấm đúp `xuong_phim\chay_xuong_phim.bat`.
- **macOS/Linux:** chạy `xuong_phim/chay_xuong_phim.sh`.

Rồi vào `http://127.0.0.1:8765/` (trình duyệt tự mở). Trong thẻ **Thiết lập**, bạn có thể:
- tải mô hình bằng nút bấm thay cho dòng lệnh;
- cài thành ứng dụng;
- bật tự chạy khi mở máy;
- xem lệnh gắn agent.

Dùng agent để cài: mở thư mục này bằng Claude Code (hoặc agent khác đọc `AGENTS.md`) rồi nói "cài Xưởng phim cho máy này".

## Triển khai giao diện lên Coolify (tuỳ chọn)

Dùng khi muốn mở Xưởng phim từ tên miền HTTPS riêng. Máy chủ chỉ phục vụ **trang tĩnh**, còn mô hình và tệp vẫn ở trên máy từng người dùng; trang gọi về `http://127.0.0.1:8765`.

1. Coolify → New Resource → kho này → Build Pack **Dockerfile**, cổng **80**, gán tên miền → Deploy. Có thể dùng `docker-compose.yml` thay thế.
2. Trên mỗi máy, chạy Xưởng phim rồi mở tên miền. Trang hiện nút **Mở trang cho phép**; bấm **Cho phép** trên trang của máy, rồi quay lại bấm **Thử lại**. Xưởng phim chỉ trả lời các trang đã được cho phép như vậy.

Chi tiết: `xuong_phim/HUONG_DAN_XUONG_PHIM.md`.

## Bố cục

```
xuong_phim/        giao diện (web/), máy chủ, trình cài, danh mục mô hình, ghép phim, MCP
tao_video_amd/     tạo video qua sd-cli (Wan2.2, Wan2.1); sd/ và models/ do trình cài tải về
long_tieng/        lồng tiếng VieNeu
tao_video/         (tuỳ chọn) Wan2.1 qua OpenVINO cho GPU Intel
mau_phim/          hai phim mẫu dựng bằng HyperFrames
Dockerfile, trien_khai/, docker-compose.yml   bản giao diện tĩnh cho Coolify
```

## Mức đã kiểm chứng

- **Windows 11** (i7-1260P, Intel Iris Xe, 16 GB): đã chạy thật toàn bộ.
  - Clip Wan2.2 640×352 dài 2 giây mất 140 giây, dài 5 giây mất khoảng 10 phút.
  - Lồng tiếng 2 câu mất 14 giây.
- **Linux:** giao diện, hàng đợi, ghép phim và MCP đã thử trong container Ubuntu 24.04, với sd-cli và VieNeu giả. Chưa thử GPU thật.
- **macOS:** chưa thử.
- **Coolify:** chưa thử trên tên miền thật.
- **Đề xuất mô hình cho máy khác máy gốc:** ước lượng.

## Dùng có trách nhiệm

Chỉ dựng hình và nhân bản giọng của chính bạn hoặc người đã đồng ý. Không làm video giả mạo người khác.

## Giấy phép của thành phần bên thứ ba

Các mô hình và chương trình do trình cài tải về từ nguồn gốc, kho này không chứa chúng.

| Thành phần | Giấy phép |
|---|---|
| Wan2.2 TI2V-5B (bản GGUF Turbo), Wan2.1 1.3B | Apache 2.0 |
| stable-diffusion.cpp | MIT |
| TAEHV | MIT |
| VieNeu-TTS | xem trang của dự án |
| FLUX.2 klein 4B | Apache 2.0 |

Kho này chưa kèm tệp giấy phép cho phần mã của Xưởng phim.
