// Service worker của Xưởng phim: chỉ giữ vỏ giao diện để mở được khi không có mạng (bản trên tên miền) hoặc khi
// Xưởng phim trên máy chưa chạy. Không lưu đệm API, ảnh, video: mọi dữ liệu luôn lấy trực tiếp từ máy.
const BO_NHO = "xuong-phim-v2";
const VO = ["/", "/ngoai_tuyen.html", "/manifest.webmanifest", "/icon.svg", "/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(BO_NHO).then(c => c.addAll(VO)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== BO_NHO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/") || u.pathname.startsWith("/tep/")) return;
  // mạng trước, hỏng mạng thì dùng bản đã lưu; trang chính không có thì về trang hướng dẫn mở Xưởng phim
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && VO.includes(u.pathname)) { const c = r.clone(); caches.open(BO_NHO).then(b => b.put(e.request, c)); }
    return r;
  }).catch(() => caches.match(e.request).then(r => r || (e.request.mode === "navigate" ? caches.match("/ngoai_tuyen.html") : Response.error()))));
});
