// Reporta al servidor los errores que ocurren en el teléfono del usuario (sin datos personales),
// para poder diagnosticar pantallas que no cargan. Máximo 5 reportes distintos por sesión.
import { API_URL } from './network.js'

const enviados = new Set()
let total = 0

export function reportarError(tipo, mensaje, extra = {}) {
  try {
    const msg = String(mensaje || '').slice(0, 400)
    const clave = tipo + msg
    if (enviados.has(clave) || total >= 5) return
    enviados.add(clave)
    total++

    let usuarioId = null
    try { usuarioId = (JSON.parse(localStorage.getItem('user') || 'null') || {}).id ?? null } catch { /* sin sesión */ }

    const cuerpo = JSON.stringify({
      tipo,
      mensaje: msg,
      ruta: location.pathname,
      usuario_id: usuarioId,
      ua: navigator.userAgent.slice(0, 200),
      version: typeof __BUILD__ !== 'undefined' ? __BUILD__ : '',
      sw: !!(navigator.serviceWorker && navigator.serviceWorker.controller),
      ...extra,
    })
    const url = `${API_URL}/errores-cliente`
    // text/plain evita la comprobación previa de CORS y sendBeacon sobrevive a recargas
    if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([cuerpo], { type: 'text/plain' }))
    else fetch(url, { method: 'POST', body: cuerpo, headers: { 'Content-Type': 'text/plain' }, keepalive: true }).catch(() => {})
  } catch { /* el reporte nunca debe romper la app */ }
}

export function iniciarReporteErrores(app) {
  window.addEventListener('error', (e) => {
    reportarError('error', `${e.message} @${String(e.filename || '').split('/').pop()}:${e.lineno}`)
  })
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason
    reportarError('promesa', (r && (r.message || String(r))) || 'rechazo sin detalle')
  })
  app.config.errorHandler = (err, _inst, info) => {
    reportarError('vue', `${(err && err.message) || err} | ${info}`)
    console.error(err)
  }
}

// Recuperación total: borra cachés y service workers viejos y recarga (arregla versiones mezcladas)
export async function recuperarApp() {
  if (!navigator.onLine) return // sin internet no se borra nada: la app abre desde su memoria
  try {
    if (navigator.serviceWorker) {
      const regs = await navigator.serviceWorker.getRegistrations()
      await Promise.all(regs.map((r) => r.unregister()))
    }
    if (window.caches) {
      const claves = await caches.keys()
      await Promise.all(claves.map((k) => caches.delete(k)))
    }
  } catch { /* seguimos con la recarga */ }
  location.reload()
}
