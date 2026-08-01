const CACHE_NAME = "cuistot-v2";
const ASSETS = [
  "/", 
  "/menu/",
  "/static/css/main.css",
  "/static/js/push.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

// Installer le service worker et mettre en cache les assets essentiels
self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Activer le service worker et prendre le contrôle des clients
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Gestion du fetch → renvoyer depuis cache si disponible
self.addEventListener("fetch", e => {
  e.respondWith(
    caches.match(e.request).then(res => res || fetch(e.request))
  );
});

// Gestion des notifications push
self.addEventListener("push", e => {
  let data = { title: "Notification", body: "Vous avez un nouveau message" };
  if (e.data) {
    data = e.data.json();
  }

  self.registration.showNotification(data.title, {
    body: data.body,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    vibrate: [200, 100, 200],
    tag: "push-notif"
  });
});

// Click sur la notification → focus ou ouvrir la page
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: "window" }).then(windowClients => {
      for (let client of windowClients) {
        if (client.url === "/" && "focus" in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow("/");
    })
  );
});
