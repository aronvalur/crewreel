// Service worker: shows new-quote alerts and opens the inbox when tapped.
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { title: "Crewreel", body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "New quote request", {
    body: d.body || "", icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", data: { url: d.url || "/quotes" }, tag: "quote",
    renotify: true,
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/quotes";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => {
    for (const w of ws) if ("focus" in w) { w.navigate(url); return w.focus(); }
    return self.clients.openWindow(url);
  }));
});
