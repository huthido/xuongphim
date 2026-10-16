# Bản giao diện Xưởng phim để triển khai trên Coolify (hoặc bất kỳ máy chủ Docker nào).
# Chỉ phục vụ trang tĩnh + PWA: mọi việc (mô hình, tệp, hàng đợi) vẫn chạy trên máy của người dùng,
# trang gọi về http://127.0.0.1:8765. Không cần đăng nhập, không lưu dữ liệu trên máy chủ.
FROM nginx:1.27-alpine
COPY trien_khai/nginx.conf /etc/nginx/conf.d/default.conf
COPY trien_khai/xuong_phim_header.inc /etc/nginx/conf.d/xuong_phim_header.inc
COPY xuong_phim/web/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
