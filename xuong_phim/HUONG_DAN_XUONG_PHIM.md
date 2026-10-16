# Xưởng phim: giao diện làm phim trên trình duyệt

Ứng dụng có giao diện để người dùng tự làm phim ngắn mà không cần gõ lệnh. Quy trình gồm năm bước:

1. **Ảnh nhân vật:** tạo ảnh rõ mặt bằng FLUX.2 klein, hoặc tải ảnh có sẵn lên.
2. **Tạo video:** cho nhân vật trong ảnh chuyển động bằng Wan2.2 5B, hoặc tạo cảnh chỉ từ lời mô tả bằng Wan2.1 1.3B.
3. **Lồng tiếng:** đọc lời thoại tiếng Việt bằng VieNeu; chọn được giọng và cao độ.
4. **Ghép phim:** nối các clip, đặt lời thoại vào từng cảnh, thêm nhạc nền.
5. **Thư viện:** xem, tải về, xoá và tải lên ảnh, video, tiếng.

Phần dưới viết cho người dùng và cho agent (Claude Code hoặc tương tự) cài trên máy mới.

**Mọi việc chạy trên máy của người dùng, không cần đăng nhập.** Giao diện mở ở `http://127.0.0.1:8765/`, hoặc cài thành ứng dụng (PWA). Có thể triển khai thêm bản giao diện lên một tên miền (ví dụ trên Coolify), nhưng bản đó chỉ là trang tĩnh: nó gọi về Xưởng phim trên máy người dùng, sau khi người dùng bấm cho phép tên miền đó một lần.

## Chạy trên hệ điều hành nào

Ứng dụng chỉ cần **Python 3.9 trở lên** (thư viện chuẩn, không cài thêm gói) và **ffmpeg**. Giao diện mở trong trình duyệt bất kỳ, chỉ nghe ở `127.0.0.1` nên máy khác trong mạng không vào được.

| Phần | Windows | Linux | macOS |
|---|---|---|---|
| Giao diện, hàng đợi, thư viện, ghép phim (`xuong_phim.py`, `ghep_phim.py`) | Đã chạy thật (Windows 11) | Đã chạy thật trong container Ubuntu 24.04 (Python 3.12, ffmpeg 6.1) | Viết cho cả ba hệ, chưa chạy thử |
| Tạo video qua sd-cli (`tao_video_amd/tao_video_sd.py`) | Đã chạy thật (Vulkan, Intel Iris Xe) | Phần script đã chạy trong container với sd-cli giả; sd-cli Vulkan/ROCm thật cho Ubuntu 24.04 chưa thử | Có bản sd-cli Metal cho Apple Silicon; chưa thử |
| Tạo video Wan2.1 qua OpenVINO (`tao_video/`) | Đã chạy thật | OpenVINO có bản Linux; chưa thử | Không hỗ trợ GPU Apple |
| Lồng tiếng VieNeu (`long_tieng/`) | Đã chạy thật (CPU) | Gói Python chạy CPU; chưa thử | Gói Python chạy CPU; chưa thử |
| Tạo ảnh FLUX.2 klein (`tao_anh.py`) | Đã chạy thật (Intel GPU) | OpenVINO có bản Linux; chưa thử | Không hỗ trợ GPU Apple |

Công cụ nào chưa cài thì ứng dụng báo **"Chưa dùng được: …"** ở đúng mục đó và khoá nút; các mục khác vẫn dùng bình thường. Ảnh nhân vật luôn có thể **tải lên** thay vì tạo.

## Bố cục thư mục

Ứng dụng tìm các công cụ trong thư mục **cha** của `xuong_phim/`. Muốn dùng chỗ khác thì đặt biến môi trường `XUONG_PHIM_GOC`.

```
<ROOT>/
  xuong_phim/                 ứng dụng này
    xuong_phim.py             máy chủ (Python thư viện chuẩn)
    web/                      giao diện + PWA (index.html, manifest, service worker, biểu tượng); không tải gì từ mạng
    cai_dat.py                trình cài: kiểm tra máy, đề xuất mô hình, tải mô hình, lồng tiếng, tự chạy khi mở máy
    mo_hinh.json              danh mục mô hình (tệp, kích thước, SHA256, bộ nhớ cần)
    ghep_phim.py              ghép phim bằng ffmpeg
    giong.json                danh sách giọng VieNeu (nút "Cập nhật danh sách giọng" làm mới)
    chay_xuong_phim.bat       mở trên Windows
    chay_xuong_phim.sh        mở trên macOS / Linux
    mcp_xuong_phim.py         máy chủ MCP để gắn agent (mục "Gắn agent qua MCP")
    mcp_cau_hinh_mau.json     cấu hình MCP mẫu cho Claude Desktop, Cursor...
    san_pham/                 tự tạo: anh/ video/ tieng/ phim/ tai_len/
    viec/                     tự tạo: mỗi việc một thư mục (viec.json, vao.json, log.txt)
    cau_hinh.json             tự tạo: mô hình video mặc định và kích thước cho máy này
    nguon_cho_phep.json       tự tạo: các tên miền được phép dùng Xưởng phim trên máy này
  tao_video_amd/              sd-cli + mô hình Wan2.2 5B, Wan2.1 1.3B (HUONG_DAN_CAI_TAO_VIDEO_AMD.md)
    tao_video_sd.py
  tao_video/                  (tuỳ chọn) Wan2.1 OpenVINO cho máy Intel (HUONG_DAN_CAI_TAO_VIDEO.md)
  long_tieng/                 VieNeu (HUONG_DAN_CAI_LAM_PHIM.md, bước lồng tiếng)
  tao_anh.py, fastsdcpu/      (tuỳ chọn) FLUX.2 klein, chỉ có trên máy gốc
```

## Cài

1. Cài ffmpeg:
   - Windows: `winget install --id Gyan.FFmpeg -e`
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt install ffmpeg`
2. Có Python 3.9+. Thường không phải cài riêng: file khởi chạy tự dùng Python trong `long_tieng/env` hoặc `tao_video/env` nếu đã có; không có thì dùng Python của máy (`py -3` hay `python` trên Windows, `python3` trên macOS và Linux).
3. Chép cả kho (hoặc bộ cài) vào `<ROOT>`: cần `xuong_phim/`, `tao_video_amd/` và `long_tieng/` nằm cạnh nhau.
4. Kiểm tra máy và cài theo đề xuất. Chọn một trong hai cách:
   - **Trên giao diện:** mở Xưởng phim → thẻ **Thiết lập** → mục 1 xem cấu hình máy và mô hình đề xuất → bấm **Tải và dùng đề xuất này**. Việc tải chạy trong Hàng đợi.
   - **Dòng lệnh:**
     ```bash
     python xuong_phim/cai_dat.py kiem_may     # in cấu hình máy và đề xuất; thêm --json để agent đọc
     python xuong_phim/cai_dat.py de_xuat      # tải sd-cli + mô hình đề xuất (vài GB), dựng lồng tiếng, đặt mặc định
     python xuong_phim/cai_dat.py kiem         # kiểm tra những gì đã cài
     ```
   Tải bị ngắt thì chạy lại cùng lệnh: trình cài tải tiếp phần còn thiếu. Mỗi tệp được so kích thước và SHA256 với `mo_hinh.json`. Lồng tiếng dùng `uv` nếu có; không có thì dùng `venv` + `pip` của Python đang chạy (bản đã thử là Python 3.11).

**Kiểm tra:** chạy `python xuong_phim.py --khong-mo` (hoặc `python3`). Dòng đầu phải in ra `Xuong phim dang chay: http://127.0.0.1:8765/`. Tiếp theo chạy `curl -s http://127.0.0.1:8765/api/trang_thai` (Windows PowerShell: `curl.exe`). Trong kết quả, mục `cong_cu` cho biết công cụ nào đã có (`"co": true`); mục nào `false` thì kèm `ly_do`.

## Mở ứng dụng

- **Windows:** bấm đúp `chay_xuong_phim.bat`. Một cửa sổ đen hiện ra và trình duyệt tự mở. Đóng cửa sổ đen là tắt ứng dụng.
- **macOS / Linux:** lần đầu chạy `chmod +x chay_xuong_phim.sh`, sau đó chạy `./chay_xuong_phim.sh`. Bấm Ctrl+C để tắt.
- **Tuỳ chọn:**
  - `--cong 9000`: đổi cổng. Mặc định 8765; nếu cổng bận, ứng dụng tự thử cổng kế tiếp.
  - `--khong-mo`: không tự mở trình duyệt.

Trình duyệt không tự mở thì vào địa chỉ in ở dòng đầu.

## Kiểm tra máy và chọn mô hình

`cai_dat.py` (và thẻ Thiết lập, công cụ MCP `kiem_may`) đọc CPU, RAM, GPU, bộ nhớ GPU và ổ đĩa trống:
- Windows đọc registry.
- Linux đọc `/sys/class/drm` và `nvidia-smi`.
- macOS dùng `system_profiler`.
- Nếu đã có sd-cli, công cụ dùng thêm `sd-cli --list-devices` để biết chắc GPU có dùng chung RAM hay không.

Từ đó tính **bộ nhớ dành cho video**:
- GPU rời: 90% bộ nhớ GPU.
- GPU tích hợp dùng chung RAM: 95% RAM trên Windows/Linux, 75% trên Mac.
- Không có GPU: 80% RAM, chạy bằng CPU (rất chậm).

Tiếp theo, công cụ chọn trong `mo_hinh.json` phương án có chất lượng tốt nhất mà vừa bộ nhớ. Thứ tự ưu tiên:
1. Họ mô hình: Wan2.2 giữ được mặt nhân vật nên đứng trên Wan2.1.
2. Khung hình lớn: 1280×704, rồi 832×480, rồi 640×352.
3. Bản nén ít mất chi tiết: Q8, rồi Q6, rồi Q4.

GPU rời thiếu bộ nhớ nhưng RAM đủ thì công cụ thêm `--offload-to-cpu`.

| Mô hình | Bộ nhớ mô hình | Nguồn số |
|---|---|---|
| Wan2.2 5B Turbo Q8_0 + umT5 Q8 | 11,5 GB | ước lượng theo kích thước tệp, chưa chạy thử |
| Wan2.2 5B Turbo Q6_K | 8,2 GB | ước lượng, chưa chạy thử |
| Wan2.2 5B Turbo Q4_K_M | 7,3 GB | đã đo |
| Wan2.1 1.3B + CausVid | 6,9 GB | đã đo |

Bộ nhớ làm việc ước khoảng 12 GB ở 832×480 (121 khung) và tăng theo số điểm ảnh. Ví dụ đề xuất:

| Máy | Đề xuất |
|---|---|
| i7-1260P, Iris Xe, 16 GB (máy gốc, đã chạy thật) | Wan2.2 Q4, 640×352 |
| 32 GB RAM, GPU tích hợp Radeon 780M | Wan2.2 Q8 + umT5 Q8, 832×480 (ước lượng) |
| 16 GB RAM, RTX 3060 12 GB | Wan2.2 Q8 + umT5 Q8, 640×352, `--offload-to-cpu` (ước lượng) |
| 8 GB RAM, GPU tích hợp | không có mô hình video vừa; vẫn dùng được lồng tiếng và ghép phim |

Đề xuất được đặt làm **mô hình mặc định**, lưu ở `cau_hinh.json`. Thẻ Tạo video chỉ liệt kê các mô hình đã tải, chọn sẵn mô hình mặc định và đánh dấu kích thước "đề xuất cho máy này". Thêm mô hình mới vào quy trình: thêm tệp vào mục `tep` và một mục vào `video` trong `mo_hinh.json`.

## Dùng như ứng dụng (PWA) và tự chạy khi mở máy

- **Cài ứng dụng:** mở `http://127.0.0.1:8765/` bằng Chrome hoặc Edge rồi bấm **Cài ứng dụng** (góc trên, hoặc thẻ Thiết lập → mục 4). Xưởng phim có biểu tượng và cửa sổ riêng như một ứng dụng.
- **Tự chạy khi mở máy:** thẻ Thiết lập → mục 4 → **Bật**, hoặc chạy `python xuong_phim/cai_dat.py tu_khoi_dong bat` (`tat` để tắt). Xưởng phim chạy nền, không hiện cửa sổ, nên bấm biểu tượng ứng dụng là dùng được ngay. Cách bật trên từng hệ điều hành:
  - Windows: lối tắt `pythonw` trong thư mục Startup.
  - macOS: LaunchAgent.
  - Linux: dịch vụ `systemd --user`.
- Xưởng phim chưa chạy thì ứng dụng hiện trang hướng dẫn mở nó. Mở xong thì trang tự kết nối lại.
- Đã thử trên Windows (16/10/2026): Chrome cho cài, service worker chạy, lối tắt tự chạy được tạo và gỡ đúng. Tự chạy trên macOS và Linux chưa thử.

## Triển khai giao diện lên Coolify (tuỳ chọn)

Dùng khi muốn mở Xưởng phim từ một tên miền HTTPS của mình, ví dụ để cài PWA trên nhiều máy từ cùng một địa chỉ. Máy chủ chỉ phục vụ trang tĩnh (nginx, thư mục `xuong_phim/web`), không chạy mô hình, không giữ tệp, không có tài khoản.

1. Coolify: **New Resource** → kho GitHub này → Build Pack **Dockerfile** (tệp `Dockerfile` ở gốc kho), cổng **80**, gán tên miền → **Deploy**. Có thể dùng `docker-compose.yml` thay thế.
2. Trên mỗi máy: chạy Xưởng phim (hoặc bật tự chạy), rồi mở tên miền. Trang báo "chưa được phép" và có nút **Mở trang cho phép**. Nút này mở trang ngay trên máy (`http://127.0.0.1:8765/cho_phep`); bấm **Cho phép**, quay lại bấm **Thử lại**.
3. Chrome/Edge có thể hỏi thêm quyền "truy cập thiết bị trong mạng cục bộ" cho tên miền đó (Local Network Access): chọn Cho phép.

**An toàn:**
- Xưởng phim trên máy chỉ trả lời các trang có trong `nguon_cho_phep.json`.
- Danh sách này chỉ sửa được từ chính trang trên máy (`127.0.0.1`), nên một trang ngoài không tự cho phép được chính nó.
- Trang chưa được phép không lấy được mã xác thực, nên không gửi được lệnh nào.
- Xem và bỏ các trang đã cho phép ở thẻ Thiết lập → mục 5.

**Đã thử:** giả lập bằng một trang ở cổng khác trên máy (`http://localhost:9000`). Đã đạt:
- Trang báo chưa được phép.
- Bấm cho phép thì trang kết nối được, đọc được thư viện, ảnh xem trước tải thẳng từ máy, và xếp được việc lồng tiếng.

Chưa thử với tên miền HTTPS thật trên Coolify.

## Dùng

Nên làm theo thứ tự các thẻ:

1. **Ảnh nhân vật.** Viết lời mô tả bằng tiếng Anh, tạo 2–3 ảnh rồi chọn ảnh đẹp nhất. Mỗi ảnh mất khoảng 1,5 phút trên Iris Xe. Có ảnh sẵn thì bấm **Tải lên…**.
2. **Tạo video.**
   - Chọn Wan2.2 5B, chọn ảnh khung đầu, rồi mô tả chuyển động bằng tiếng Anh theo thứ tự động tác.
   - Cỡ 640×352 vừa máy 16 GB RAM. Cỡ 832×480 cần GPU rời hoặc từ 32 GB RAM.
   - Ứng dụng hiện thời gian ước tính, tính theo số đo trên Iris Xe.
   - Ở thẻ Thư viện, nút **Làm video** trên một ảnh sẽ chuyển thẳng sang bước này với ảnh đó.
3. **Lồng tiếng.** Mỗi dòng gồm giọng, cao độ và câu thoại. Giọng trẻ em: lấy giọng nữ trẻ (ví dụ Trúc Ly) và nâng cao độ +3.
4. **Ghép phim.** Mỗi cảnh gồm clip, lời thoại (tuỳ chọn), **Trễ** (số giây sau khi cảnh bắt đầu thì nhân vật nói) và **Bỏ đầu** (cắt bớt đầu clip nếu bị giật). Lời thoại dài hơn clip thì khung cuối được giữ lại cho đến khi nói xong. Có thể thêm nhạc nền và chỉnh âm lượng; nhạc tự lặp lại và nhỏ dần ở 2 giây cuối.
5. **Hàng đợi** ở cột phải.
   - Mỗi lần chỉ chạy **một việc**; việc mới xếp hàng phía sau.
   - Việc đang chạy hiện nhật ký trực tiếp. Bấm **Huỷ** hai lần để dừng; lệnh này dừng cả sd-cli và ffmpeg đang chạy bên dưới.
   - Việc xong hiện ngay ảnh, video hoặc tiếng vừa tạo. **Chạy lại** tạo lại việc với cùng thông số.
   - Đóng trình duyệt không làm dừng việc. Tắt ứng dụng (đóng cửa sổ đen) thì việc đang chạy bị dừng.

**Chỉ dựng hình và nhân bản giọng của chính mình hoặc người đã đồng ý.** Không làm video giả mạo người khác.

## Các quy tắc ứng dụng tự giữ

- **Một việc mỗi lần, và bước trước nhả hết tài nguyên rồi bước sau mới chạy.** Mỗi việc là một chương trình riêng (sd-cli, VieNeu, ffmpeg…). Xong là chương trình thoát hẳn, nên hệ điều hành thu lại toàn bộ RAM và bộ nhớ GPU của việc đó. Lúc rảnh chỉ còn máy chủ của ứng dụng, khoảng 50 MB. Đã kiểm trên máy gốc: sau mỗi việc, kể cả việc bị huỷ, không còn tiến trình nào sót lại.
- **Kiểm RAM trống trước mỗi việc.** Chưa đủ thì việc hiện **Chờ RAM**, kèm tên các ứng dụng đang chiếm nhiều RAM để người dùng đóng bớt; đủ thì việc tự bắt đầu. Nút **Chạy luôn** bỏ qua bước chờ; máy có thể chậm hoặc đơ. Ứng dụng **không tự đóng** chương trình khác của người dùng. Mức cần:

  | Việc | RAM trống cần | Nguồn số |
  |---|---|---|
  | Video, máy GPU dùng chung RAM | bộ nhớ mô hình + bộ nhớ làm việc − 8,1 GB, tối thiểu 6 GB | Đo: Wan2.2 Q4 640×352 cần 14,1 GB, bắt đầu với 6,2 GB trống vẫn chạy được (Windows tự dồn bớt ứng dụng khác) |
  | Video, máy có GPU rời | 4 GB (cộng bộ nhớ mô hình nếu `--offload-to-cpu`) | Ước lượng, chưa đo |
  | Tạo ảnh | 4 GB | Ước lượng, chưa đo |
  | Lồng tiếng | 1,5 GB | Ước lượng (mô hình 0,76 GB) |
  | Ghép phim, cài đặt | 0,5 GB / 0,3 GB | Ước lượng |

  Muốn đổi thì sửa hàm `ram_can` trong `xuong_phim.py`.
- Các việc chạy đúng thứ tự đã xếp. Việc đầu hàng đang chờ RAM thì các việc sau cũng chờ, vì việc sau có thể cần kết quả của việc trước (ví dụ ghép phim cần clip vừa tạo).
- **Giữ máy không tự ngủ** trong lúc có việc chạy:
  - Windows dùng `SetThreadExecutionState`.
  - macOS dùng `caffeinate`.
  - Linux dùng `systemd-inhibit`.
  - Riêng gập nắp máy thì máy vẫn ngủ.
- **Không tự chạy lại.** Việc đang chạy hay đang chờ khi ứng dụng tắt sẽ được đánh dấu **Bị ngắt**; người dùng tự bấm Chạy lại. Nếu tệp kết quả đã có đủ thì đánh dấu **Xong**.
- **An toàn:**
  - Chỉ nghe ở 127.0.0.1.
  - Từ chối yêu cầu có `Host` lạ, để chặn DNS rebinding.
  - Mọi lệnh ghi phải kèm mã ngẫu nhiên sinh mỗi lần mở ứng dụng; trang web khác không gửi lệnh được.
  - Tệp chỉ đọc và ghi trong `san_pham/`.
  - Thông số đưa vào công cụ qua file JSON, không ghép vào dòng lệnh.

## Lỗi thường gặp

| Hiện tượng | Cách sửa |
|---|---|
| Mục nào đó báo "Chưa dùng được" | Thẻ Thiết lập: bấm "Tự cài" hoặc làm theo lệnh hiện ở đó, rồi bấm "Kiểm tra lại" |
| Việc **Lỗi** | Bấm **Nhật ký** xem dòng cuối. Đọc thư mục `viec/<mã việc>/log.txt` để xem đầy đủ |
| Tạo video báo `device lost` hoặc máy đơ | Thiếu bộ nhớ: đóng bớt ứng dụng, chọn cỡ nhỏ hơn hoặc ngắn hơn |
| Lồng tiếng lần đầu chậm | VieNeu tải mô hình (0,76 GB) về bộ đệm Hugging Face; cần mạng lần đầu |
| `khong mo duoc cong nao` | 20 cổng từ 8765 đều bận; chạy với `--cong 9100` |
| macOS báo sd-cli "không xác minh được nhà phát triển" | `xattr -dr com.apple.quarantine <ROOT>/tao_video_amd/sd` |

## Gắn agent qua MCP

`mcp_xuong_phim.py` là máy chủ MCP qua stdio. Nó chỉ dùng thư viện chuẩn của Python 3.9+, chạy trên Windows, Linux và macOS. Agent hỗ trợ MCP (Claude Code, Claude Desktop, Cursor, VS Code…) gắn vào là tự làm phim được, đồng thời xem được ảnh và khung hình để tự đánh giá kết quả.

**Đăng ký:**

- **Claude Code:**
  ```bash
  claude mcp add xuong-phim -- <python> -I <ROOT>/xuong_phim/mcp_xuong_phim.py
  ```
  - `<python>` là Python 3.9+ bất kỳ, ví dụ `<ROOT>/long_tieng/env/Scripts/python.exe` (Windows), `<ROOT>/long_tieng/env/bin/python` hoặc `python3` (macOS/Linux).
  - Thêm `-s user` để dùng ở mọi thư mục.
  - Mở phiên mới (hoặc gõ `/mcp`) để agent thấy các công cụ.
- **Claude Desktop, Cursor và các ứng dụng khác:** chép nội dung `mcp_cau_hinh_mau.json` vào tệp cấu hình MCP của ứng dụng, sửa đường dẫn. Ví dụ với Claude Desktop là `claude_desktop_config.json`.

**Kiểm tra:** `claude mcp get xuong-phim` báo `✔ Connected`.

**Cách hoạt động:**
- MCP gọi API của `xuong_phim.py`, nên mọi quy tắc của ứng dụng vẫn giữ: một việc mỗi lần, chờ đủ RAM, tệp chỉ trong `san_pham/`. Agent và người dùng trên trình duyệt dùng chung một hàng đợi và một thư viện.
- Xưởng phim chưa chạy thì MCP tự mở nền (không mở trình duyệt; nhật ký ở `may_chu_log.txt`). Việc vẫn chạy tiếp khi agent thoát.
- Chỉ một bản Xưởng phim chạy mỗi lúc: bản mở sau đọc `.may_chu.json`, thấy bản cũ còn sống thì chỉ mở trình duyệt tới bản đó.

**Công cụ cho agent:**

| Công cụ | Việc |
|---|---|
| `trang_thai` | Công cụ đã cài, RAM, ứng dụng chiếm RAM, việc gần đây |
| `danh_sach_tep`, `danh_sach_giong` | Thư viện (kèm `ref` và đường dẫn), giọng VieNeu |
| `tao_anh`, `tao_video`, `long_tieng`, `ghep_phim` | Xếp việc; trả về `id`. `tao_video` nhận `giay` (2–5) hoặc `frames` |
| `cho_viec` | Chờ việc xong (mặc định 300 giây, tối đa 1800), trả tệp ra hoặc nhật ký lỗi |
| `xem_viec` | Trạng thái và cuối nhật ký, không chờ |
| `xem_tep` | Ảnh: trả ảnh thu nhỏ. Video: trả lưới 6 khung hình trải đều. Âm thanh: độ dài (agent không nghe được) |
| `tai_len` | Đưa tệp trên máy vào thư viện |
| `huy_viec`, `chay_lai`, `chay_luon`, `xoa_tep` | Huỷ; chạy lại; bỏ qua chờ RAM; xoá tệp. `chay_luon` và `xoa_tep` chỉ dùng khi người dùng đồng ý |
| `kiem_may` | Cấu hình máy và mô hình đề xuất (kèm phương án khác, cảnh báo) |
| `danh_muc_mo_hinh` | Mô hình đã tải, cần tải bao nhiêu, mô hình mặc định |
| `cai_dat` | Xếp việc cài: `de_xuat`, `mo_hinh`, `sd_cli`, `long_tieng`, `tu_khoi_dong`. Tải nhiều GB: agent phải hỏi người dùng trước |
| `dat_mac_dinh` | Đặt mô hình video mặc định và kích thước |

Khi kết nối, máy chủ MCP gửi kèm hướng dẫn cho agent: thứ tự các bước, viết lời mô tả bằng tiếng Anh, mỗi clip một người, xem kết quả trước khi dùng tiếp, và phải có sự đồng ý khi dựng hình hay lồng giọng người thật.

**Đã thử (16/10/2026):**
- Windows: Claude Code kết nối được; chương trình khách thử gọi đủ các công cụ (tự mở Xưởng phim, lồng tiếng, ghép phim, xem lưới khung hình, tải lên, báo lỗi khi thông số sai).
- Container Ubuntu 24.04: với sd-cli và VieNeu giả, cả quy trình qua MCP đều chạy đúng.

## Cho agent: điều khiển bằng API

Mọi thao tác trên giao diện đều đi qua API JSON. Gọi `POST` phải kèm header `X-Token`. Lấy mã bằng `GET /api/ket_noi`; mã đổi mỗi lần Xưởng phim khởi động lại.

| Lệnh | Việc |
|---|---|
| `GET /api/ket_noi` | `{token, phien_ban, cong}`; trang ngoài chưa được phép nhận lỗi `nguon_chua_cho_phep` |
| `GET /api/may` | Cấu hình máy + đề xuất (`?moi=1` để đọc lại) |
| `GET /api/mo_hinh`, `POST /api/cau_hinh` | Danh mục mô hình; đặt mô hình mặc định `{id, w, h, extra}` |
| `GET /api/thiet_lap` | Đường dẫn, lệnh gắn MCP, tự chạy, trang được phép |
| `POST /api/nguon` | `{nguon, them}`: thêm/bớt trang được phép (chỉ từ chính máy) |
| `GET /cho_phep?nguon=https://...` | Trang để người dùng bấm cho phép một tên miền |
| `GET /api/trang_thai` | Công cụ đã có, RAM, danh sách việc |
| `GET /api/viec/<id>` | Một việc kèm cuối nhật ký |
| `GET /api/tep` | Tệp trong thư viện; mỗi tệp có `ref` dạng `loai/ten` |
| `POST /api/viec` | Thêm việc. Ví dụ: `{"loai":"video","mo_hinh":"wan22_5b_q4","anh":"anh/x.png","prompt":"...","w":640,"h":352,"frames":121,"seed":7}` (`mo_hinh` là id trong `mo_hinh.json`; `wan22` = mặc định của máy). Các loại khác: `anh` (prompt, w, h, so_anh, seed, ref), `tieng` (dong: [{giong, cao_do, cau}]), `ghep` (canh: [{video, tieng, tre, bo_dau}], nhac, am_luong_nhac, w, h, ten), `giong`, `cai` (lenh, tham_so) |
| `POST /api/viec/<id>/huy`, `/chay_lai`, `/chay_luon` | Huỷ; chạy lại; bắt đầu ngay dù đang chờ RAM |
| `POST /api/tai_len?ten=<tên tệp>` | Thân yêu cầu là nội dung tệp |
| `GET /tep/<loai>/<ten>` | Tải tệp về (hỗ trợ Range) |

## Số đo trên máy gốc (i7-1260P, Intel Iris Xe, 16 GB, Windows 11)

| Việc | Thời gian |
|---|---|
| Lồng tiếng 2 câu (gồm nạp mô hình 11 giây) | 14 giây |
| Video Wan2.2 5B, 640×352, 49 khung (2 giây) từ ảnh | 140 giây (tạo chuyển động 119 giây, giải mã 4 giây) |
| Video Wan2.2 5B, 640×352, 121 khung (5 giây) từ ảnh | khoảng 10 phút (tạo chuyển động 491 giây, giải mã 32 giây; đo bằng lệnh sd-cli trực tiếp) |
| Ghép phim 2 cảnh có lời thoại, 1280×720 | 3 giây |
| Huỷ một việc tạo video đang chạy | sd-cli dừng ngay, không còn tiến trình sót |

Đo ngày 16/10/2026, cả quy trình bấm trên giao diện.

**Thử trên Linux (16/10/2026):** container `ubuntu:24.04` (Python 3.12.3, ffmpeg 6.1.1), dùng sd-cli và VieNeu **giả** vì container không có GPU. Đã đạt:
- Phát hiện công cụ đúng; đọc RAM từ `/proc/meminfo`.
- Ảnh 1248×720 được cắt về 640×352 trước khi đưa cho sd-cli.
- Lời mô tả có `"` và dấu tiếng Việt không làm hỏng lệnh.
- Ghép 2 cảnh (một clip dọc 352×640 được thêm viền) kèm lời thoại và nhạc nền.
- Huỷ việc dừng cả nhóm tiến trình (`killpg`).
- Khởi động lại khi còn việc chờ thì việc đó được đánh dấu "Bị ngắt".

Chưa thử: sd-cli thật trên GPU Linux, VieNeu thật trên Linux, và mọi thứ trên macOS. Clip Wan2.2 đôi khi có vệt màu lóe 1–2 khung (xem Phần B của hướng dẫn AMD); đổi seed để thử lại.
