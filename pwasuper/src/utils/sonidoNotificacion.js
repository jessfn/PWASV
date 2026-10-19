// Sonido de las notificaciones: un "ding" suave y moderno, una sola vez por cada notificación nueva.
//
// Reglas (para que NUNCA suene como repetidora):
//  - El sonido se decide por la IDENTIDAD de la notificación (su id), no por cambios en un contador.
//    Cada id suena una sola vez en este dispositivo (se recuerda en el teléfono).
//  - Nunca suena al abrir la app ni por avisos que ya existían: la primera carga solo "aprende" lo que ya hay.
//  - Máximo un ding cada 4 segundos, aunque lleguen varias a la vez.
//  - Solo suena con la app a la vista. Con la app cerrada o en segundo plano suena el aviso del propio teléfono.
//  - El sonido se sintetiza (sin archivos): no pesa nada y funciona sin internet.

const PREF = 'sonido_avisos'
const MIN_ENTRE_DINGS_MS = 4000
let contexto = null
let ultimoDing = 0
let listo = false

export const sonidoActivado = () => {
  try { return localStorage.getItem(PREF) !== 'off' } catch { return true }
}
export const activarSonido = (si) => {
  try { localStorage.setItem(PREF, si ? 'on' : 'off') } catch { /* sin almacenamiento */ }
}

function obtenerContexto() {
  if (!contexto) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return null
    contexto = new AC()
  }
  return contexto
}

/**
 * Los navegadores solo permiten sonido después de que la persona toca la pantalla.
 * Se prepara el audio en el primer toque (una sola vez) para que luego los avisos puedan sonar.
 */
export function prepararSonido() {
  if (listo) return
  listo = true
  const desbloquear = () => {
    try {
      const c = obtenerContexto()
      if (c && c.state === 'suspended') c.resume()
    } catch { /* sin audio */ }
    ['pointerdown', 'touchend', 'keydown'].forEach((e) => window.removeEventListener(e, desbloquear, true))
  }
  ['pointerdown', 'touchend', 'keydown'].forEach((e) => window.addEventListener(e, desbloquear, { capture: true, passive: true }))
}

/** El "ding": dos parciales de campana (re 6 y su octava) con ataque suave y caída larga. */
export function ding() {
  try {
    const c = obtenerContexto()
    if (!c) return false
    if (c.state === 'suspended') c.resume()
    if (c.state !== 'running') return false   // aún sin permiso del navegador: no se fuerza
    const t = c.currentTime
    const salida = c.createGain()
    salida.gain.value = 0.55
    salida.connect(c.destination)

    const nota = (frecuencia, pico, caida) => {
      const o = c.createOscillator()
      const g = c.createGain()
      o.type = 'sine'
      o.frequency.setValueAtTime(frecuencia, t)
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(pico, t + 0.012)          // ataque suave
      g.gain.exponentialRampToValueAtTime(0.0001, t + caida)        // caída larga
      o.connect(g); g.connect(salida)
      o.start(t); o.stop(t + caida + 0.05)
    }
    nota(1174.66, 0.2, 1.0)    // re 6: el cuerpo del ding
    nota(2349.32, 0.07, 0.45)  // octava: el brillo
    nota(587.33, 0.05, 0.7)    // re 5: un poco de calidez
    return true
  } catch {
    return false
  }
}

const claveVistas = (uid) => `notif_oidas_${uid}`
const leerVistas = (uid) => {
  try { return new Set(JSON.parse(localStorage.getItem(claveVistas(uid)) || '[]')) } catch { return new Set() }
}
const guardarVistas = (uid, set) => {
  try { localStorage.setItem(claveVistas(uid), JSON.stringify([...set].slice(-300))) } catch { /* sin almacenamiento */ }
}

/** Aprende las notificaciones que ya existen, sin sonar (carga inicial). */
export function registrarConocidas(uid, ids) {
  if (!uid || !ids || !ids.length) return
  const set = leerVistas(uid)
  ids.forEach((i) => set.add(i))
  guardarVistas(uid, set)
}

/** ¿Ya se aprendió el estado inicial de este usuario en este dispositivo? */
export const hayLineaBase = (uid) => {
  try { return localStorage.getItem(claveVistas(uid)) !== null } catch { return false }
}

/**
 * Anuncia notificaciones. Suena solo si alguna es realmente nueva para este dispositivo.
 * Devuelve true si sonó.
 */
export function anunciarNuevas(uid, ids) {
  if (!uid || !ids || !ids.length) return false
  const set = leerVistas(uid)
  const nuevas = ids.filter((i) => i != null && !set.has(i))
  if (!nuevas.length) return false
  nuevas.forEach((i) => set.add(i))
  guardarVistas(uid, set)
  if (!sonidoActivado()) return false
  if (document.visibilityState !== 'visible') return false
  const ahora = Date.now()
  if (ahora - ultimoDing < MIN_ENTRE_DINGS_MS) return false
  if (!ding()) return false
  ultimoDing = ahora
  try { if (navigator.vibrate) navigator.vibrate(30) } catch { /* sin vibración */ }
  return true
}

/** Para el botón "Escuchar" de Configuración. */
export function probarSonido() {
  prepararSonido()
  return ding()
}
