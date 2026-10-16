# Hướng dẫn cho agent: cài và dùng Xưởng phim

Bạn (agent) đang ở gốc kho **Xưởng phim**: bộ công cụ làm phim ngắn bằng AI chạy hoàn toàn trên máy người dùng. Bộ gồm:
- tạo video từ ảnh (Wan2.2 qua stable-diffusion.cpp);
- lồng tiếng tiếng Việt (VieNeu);
- ghép phim (ffmpeg);
- giao diện web/PWA và máy chủ MCP.

Thư mục này là `<ROOT>`. Trả lời người dùng bằng tiếng Việt.

## Khi người dùng nhờ "cài", "thiết lập", "chạy Xưởng phim" trên máy này

Làm lần lượt. Bước nào tải nhiều hoặc đổi cấu hình máy thì **hỏi người dùng trước**.

1. **Kiểm tra nền:** cần Python 3.9+ và ffmpeg.
   - Chạy `python --version` (hoặc `python3`, hoặc `py -3`) và `ffmpeg -version`.
   - Thiếu ffmpeg thì đề nghị cài: Windows `winget install --id Gyan.FFmpeg -e`, macOS `brew install ffmpeg`, Ubuntu `sudo apt install -y ffmpeg`.
2. **Kiểm tra máy và xem đề xuất:**
   ```bash
   python xuong_phim/cai_dat.py kiem_may          # thêm --json để đọc máy
   ```
   Báo người dùng các thông tin sau:
   - CPU, RAM, GPU (bộ nhớ riêng hay dùng chung RAM).
   - Mô hình video được đề xuất và kích thước.
   - Dung lượng cần tải.
   - Các cảnh báo.

   Số bộ nhớ chỉ được đo thật trên Intel Iris Xe 16 GB; với máy khác, nói rõ là ước lượng.
3. **Cài theo đề xuất** (khi người dùng đồng ý; tải vài GB):
   ```bash
   python xuong_phim/cai_dat.py de_xuat
   ```
   Lệnh này tải sd-cli và mô hình (kiểm SHA256), dựng môi trường lồng tiếng, rồi đặt mô hình làm mặc định.
   - Việc chạy lâu thì chạy tách khỏi agent (chạy nền, ghi nhật ký ra tệp) và theo dõi nhật ký.
   - Bị ngắt thì chạy lại cùng lệnh: trình cài tải tiếp phần còn thiếu.
4. **Kiểm tra:** `python xuong_phim/cai_dat.py kiem`. Mọi dòng cần dùng phải có `OK`.
5. **Mở Xưởng phim:**
   - Windows: `xuong_phim/chay_xuong_phim.bat`.
   - macOS/Linux: `xuong_phim/chay_xuong_phim.sh`.
   - Rồi vào `http://127.0.0.1:8765/`.
   - Hỏi người dùng có muốn tự chạy khi mở máy không. Nếu có: `python xuong_phim/cai_dat.py tu_khoi_dong bat`.
   - Gợi ý bấm **Cài ứng dụng** để dùng như PWA.
6. **Gắn agent qua MCP** (nếu người dùng muốn agent điều khiển Xưởng phim):
   ```bash
   claude mcp add xuong-phim -- <python> -I <ROOT>/xuong_phim/mcp_xuong_phim.py
   ```
   Kiểm tra bằng `claude mcp get xuong-phim`. Các agent khác: xem `xuong_phim/mcp_cau_hinh_mau.json`.

Người dùng không quen dòng lệnh thì làm cả các bước trên trong giao diện: thẻ **Thiết lập** → **Tải và dùng đề xuất này**.

## Quy tắc khi chạy trên máy người dùng

- **Mỗi lần một tiến trình nặng** (tạo video, tạo ảnh). Máy 16 GB rất sát RAM. Xưởng phim tự xếp hàng và chờ đủ RAM; đừng chạy công cụ song song bên ngoài nó.
- Tiến trình bị ngắt vì thiếu bộ nhớ thì **không tự chạy lại**; báo người dùng và đề nghị đóng bớt ứng dụng hoặc chọn cỡ nhỏ hơn.
- Không tự bấm "Chạy luôn" khi việc đang chờ RAM; hỏi người dùng.
- Không đưa mô hình (`*.gguf`, `*.safetensors`), `env/`, `san_pham/`, `viec/` vào git.
- Chỉ dựng hình và nhân bản giọng của chính người dùng hoặc người đã đồng ý. Không làm video giả mạo người khác.
- Số liệu nào chưa đo thì ghi "chưa đo"; đừng đoán.
- Sửa công cụ nào thì cập nhật hướng dẫn tương ứng.

## Tài liệu

| Tệp | Nội dung |
|---|---|
| `README.md` | Giới thiệu, cài nhanh, triển khai Coolify |
| `xuong_phim/HUONG_DAN_XUONG_PHIM.md` | Giao diện, trình cài, chọn mô hình, PWA, Coolify, MCP, API |
| `tao_video_amd/HUONG_DAN_CAI_TAO_VIDEO_AMD.md` | sd-cli, Wan2.2/Wan2.1, bài học khi thử (Phần B: Wan2.2) |
| `tao_video/HUONG_DAN_CAI_TAO_VIDEO.md` | Bản OpenVINO cho GPU Intel (tuỳ chọn) |
| `HUONG_DAN_CAI_LAM_PHIM.md` | Toàn bộ quy trình làm phim, dựng bằng HyperFrames, bài học, số đo |
| `xuong_phim/mo_hinh.json` | Danh mục mô hình: thêm mô hình mới ở đây |
