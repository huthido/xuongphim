# Header an toàn cho mọi trang của bản giao diện trên Coolify
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy no-referrer always;
# cấm trang khác nhúng Xưởng phim vào khung (chống clickjacking)
add_header X-Frame-Options DENY always;
add_header Content-Security-Policy "frame-ancestors 'none'" always;
