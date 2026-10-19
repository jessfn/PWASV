/* Avisos push (se carga dentro del service worker principal con importScripts).
 * Recibe el aviso del servidor aunque la app esté cerrada, lo muestra como notificación del teléfono
 * y, si la app está abierta, le avisa para que se actualice al instante. */

self.addEventListener('push', (event) => {
  let d = {};
  try {
    d = event.data ? event.data.json() : {};
  } catch (e) {
    d = { titulo: 'Sembrando Vida', cuerpo: event.data ? event.data.text() : '' };
  }
  const titulo = d.titulo || 'Sembrando Vida';
  const opciones = {
    body: d.cuerpo || '',
    icon: '/pwa-192x192.png',
    badge: '/pwa-192x192.png',
    tag: d.tag || 'aviso',
    renotify: true,
    vibrate: [120, 60, 120],
    timestamp: d.ts ? d.ts * 1000 : Date.now(),
    data: { url: d.url || '/notificaciones', id: d.id || null },
  };

  event.waitUntil((async () => {
    await self.registration.showNotification(titulo, opciones);
    try {
      // Reactivo: las ventanas abiertas refrescan su lista y su contador de inmediato
      const ventanas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      ventanas.forEach((c) => c.postMessage({ type: 'PUSH_RECIBIDO', id: d.id || null }));
      // Punto en el icono de la app mientras haya algo nuevo (la app lo pone en número al abrirse)
      if (self.navigator && self.navigator.setAppBadge) await self.navigator.setAppBadge();
    } catch (e) { /* sin soporte: la notificación igual se mostró */ }
  })());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || '/notificaciones';
  event.waitUntil((async () => {
    const url = new URL(destino, self.location.origin).href;
    const ventanas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of ventanas) {
      if (c.url.startsWith(self.location.origin) && 'focus' in c) {
        await c.focus();
        if ('navigate' in c) { try { await c.navigate(url); } catch (e) { c.postMessage({ type: 'ABRIR_RUTA', url: destino }); } }
        else c.postMessage({ type: 'ABRIR_RUTA', url: destino });
        return;
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(url);
  })());
});
