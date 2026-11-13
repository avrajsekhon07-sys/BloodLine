// Service worker for BloodLine Web Push (served from the same folder as index.html).
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data.json(); } catch (_) { d = { title: "BloodLine", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "BloodLine", { body: d.body || "", tag: "bloodline" }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: "window" }).then((l) => (l.length ? l[0].focus() : clients.openWindow("./"))));
});
