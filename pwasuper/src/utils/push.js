// Avisos push (Web Push): el teléfono recibe las notificaciones aunque la app esté cerrada (solo instalada).
// Flujo: pedir permiso -> suscribirse con la clave del servidor -> guardar el dispositivo en el servidor.
import { API_URL } from './network.js'

const SYNC_KEY = 'push_sync'
const SEIS_HORAS = 6 * 60 * 60 * 1000

export const pushSoportado = () =>
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

export const esIOS = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

export const esInstalada = () =>
  (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true

function aBytes(base64) {
  const relleno = '='.repeat((4 - (base64.length % 4)) % 4)
  const b = (base64 + relleno).replace(/-/g, '+').replace(/_/g, '/')
  const bin = atob(b)
  const salida = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) salida[i] = bin.charCodeAt(i)
  return salida
}

async function claveServidor() {
  const r = await fetch(`${API_URL}/push/clave-publica`, { cache: 'no-store' })
  const j = await r.json()
  if (!j.disponible || !j.clave) throw new Error('sin-servidor')
  return j.clave
}

const registro = () => navigator.serviceWorker.ready

async function enviarSuscripcion(usuarioId, sub) {
  const j = sub.toJSON()
  const r = await fetch(`${API_URL}/push/suscribir`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usuario_id: usuarioId, endpoint: j.endpoint, keys: j.keys, ua: navigator.userAgent }),
  })
  if (!r.ok) throw new Error('registro-fallido')
  try { localStorage.setItem(SYNC_KEY, JSON.stringify({ u: usuarioId, t: Date.now() })) } catch { /* sin almacenamiento */ }
}

/** 'activo' | 'inactivo' | 'denegado' | 'instalar' | 'no-soportado' */
export async function estadoPush() {
  if (!pushSoportado()) return { estado: esIOS() && !esInstalada() ? 'instalar' : 'no-soportado' }
  if (esIOS() && !esInstalada()) return { estado: 'instalar' }
  if (Notification.permission === 'denied') return { estado: 'denegado' }
  if (Notification.permission === 'default') return { estado: 'inactivo' }
  try {
    const sub = await (await registro()).pushManager.getSubscription()
    return sub ? { estado: 'activo', endpoint: sub.endpoint } : { estado: 'inactivo' }
  } catch {
    return { estado: 'inactivo' }
  }
}

/** Pide permiso (debe llamarse desde un toque del usuario) y registra este dispositivo. */
export async function activarPush(usuarioId) {
  if (!pushSoportado()) return { ok: false, motivo: 'no-soportado' }
  const permiso = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission()
  if (permiso !== 'granted') return { ok: false, motivo: permiso === 'denied' ? 'denegado' : 'cerrado' }
  try {
    const clave = await claveServidor()
    const reg = await registro()
    let sub = await reg.pushManager.getSubscription()
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: aBytes(clave) })
    await enviarSuscripcion(usuarioId, sub)
    return { ok: true }
  } catch (e) {
    return { ok: false, motivo: e && e.message === 'sin-servidor' ? 'sin-servidor' : 'error' }
  }
}

export async function desactivarPush() {
  try {
    const sub = await (await registro()).pushManager.getSubscription()
    if (sub) {
      const endpoint = sub.endpoint
      await sub.unsubscribe()
      await fetch(`${API_URL}/push/baja`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint }) })
    }
    return { ok: true }
  } catch {
    return { ok: false }
  }
}

export async function probarPush(usuarioId) {
  const r = await fetch(`${API_URL}/push/probar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ usuario_id: usuarioId }) })
  if (r.ok) return { ok: true }
  let detalle = ''
  try { detalle = (await r.json()).detail } catch { /* sin cuerpo */ }
  return { ok: false, detalle }
}

/**
 * Mantiene el dispositivo al día en silencio (sin pedir nada): si ya hay permiso, vuelve a registrar la
 * suscripción (también cuando otra persona inicia sesión en el mismo teléfono). Máximo cada 6 horas.
 */
export async function sincronizarPush(usuarioId) {
  try {
    if (!usuarioId || !pushSoportado() || Notification.permission !== 'granted') return
    let previo = null
    try { previo = JSON.parse(localStorage.getItem(SYNC_KEY) || 'null') } catch { /* sin datos */ }
    if (previo && previo.u === usuarioId && Date.now() - previo.t < SEIS_HORAS) return
    const reg = await registro()
    let sub = await reg.pushManager.getSubscription()
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: aBytes(await claveServidor()) })
    await enviarSuscripcion(usuarioId, sub)
  } catch { /* se reintenta en la próxima apertura */ }
}
