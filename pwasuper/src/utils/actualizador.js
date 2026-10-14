// Actualización reactiva: cada vez que se publica una versión nueva, TODAS las pantallas abiertas
// se actualizan solas (mismo aviso "Actualizando…"), sin que la persona cierre ni recargue nada.
//
// Cómo funciona:
//  1. Cada compilación escribe /version.json con su identificador (BUILD) y lo guarda dentro del código.
//  2. La app compara su BUILD con el de /version.json: cada 60 s con la pantalla visible, y también al volver
//     a abrir la app, al recuperar internet y al cambiar de pantalla.
//  3. Si difieren, espera a que no haya un envío en curso (para no perder un registro) y se actualiza.

export const BUILD = typeof __BUILD__ !== 'undefined' ? __BUILD__ : ''

const INTERVALO_MS = 60 * 1000
const MIN_ENTRE_CONSULTAS_MS = 15 * 1000
const ESPERA_MAX_OCUPADA_MS = 120 * 1000

let ultimaConsulta = 0
let consultando = false
let detenido = false
let versionDetectada = ''

// Consulta la versión publicada; devuelve su identificador si es distinta de la que está corriendo
async function versionNueva() {
  try {
    const r = await fetch(`/version.json?t=${Date.now()}`, { cache: 'no-store' })
    if (!r.ok) return ''
    const j = await r.json()
    return j && j.build && j.build !== BUILD ? String(j.build) : ''
  } catch {
    return '' // sin internet o sin archivo: no hay nada que hacer
  }
}

// Si hay un envío en curso (asistencia, actividad, foto) se espera a que termine
function esperarLibre() {
  return new Promise((resolve) => {
    const t0 = Date.now()
    const tic = () => {
      if (!window.__appOcupada || Date.now() - t0 > ESPERA_MAX_OCUPADA_MS) resolve()
      else setTimeout(tic, 3000)
    }
    tic()
  })
}

// Aplica la actualización de forma fiable: primero por el service worker y, si no responde, limpieza total.
export async function aplicarActualizacion() {
  // Freno contra bucles: máximo 4 intentos en 10 minutos
  try {
    const k = 'upd_intentos'
    const d = JSON.parse(localStorage.getItem(k) || '{}')
    const ahora = Date.now()
    const vigente = d.t && ahora - d.t < 10 * 60 * 1000
    const n = vigente ? d.n + 1 : 1
    localStorage.setItem(k, JSON.stringify({ n, t: vigente ? d.t : ahora }))
    if (n > 4) { location.reload(); return }
  } catch { /* sin almacenamiento */ }

  const limpiezaTotal = async () => {
    try {
      if (navigator.serviceWorker) {
        const regs = await navigator.serviceWorker.getRegistrations()
        await Promise.all(regs.map((r) => r.unregister()))
      }
      if (window.caches) {
        const claves = await caches.keys()
        await Promise.all(claves.map((c) => caches.delete(c)))
      }
    } catch { /* seguimos */ }
    location.replace(`${location.pathname}?v=${Date.now()}${location.hash}`)
  }

  try {
    if (!navigator.serviceWorker) return limpiezaTotal()
    const reg = await navigator.serviceWorker.getRegistration()
    if (!reg) return limpiezaTotal()

    const tomoControl = new Promise((res) => {
      navigator.serviceWorker.addEventListener('controllerchange', () => res(true), { once: true })
      setTimeout(() => res(false), 8000)
    })
    await reg.update() // baja el service worker nuevo (que trae los archivos nuevos)
    const nuevo = reg.waiting || reg.installing
    if (nuevo) {
      if (!reg.waiting) {
        await new Promise((res) => {
          nuevo.addEventListener('statechange', () => { if (nuevo.state === 'installed' || nuevo.state === 'activated') res() })
          setTimeout(res, 7000)
        })
      }
      if (reg.waiting) reg.waiting.postMessage({ type: 'SKIP_WAITING' })
    }
    if (await tomoControl) {
      setTimeout(() => location.reload(), 1200)
    } else {
      await limpiezaTotal() // el service worker no respondió: se limpia y se recarga desde la red
    }
  } catch {
    await limpiezaTotal()
  }
}

// Arranca la vigilancia. `alDetectar` muestra el aviso y aplica la actualización.
export function iniciarActualizador(alDetectar) {
  const revisar = async (forzar = false) => {
    if (detenido || consultando || !navigator.onLine) return
    if (document.visibilityState === 'hidden' && !forzar) return
    if (!forzar && Date.now() - ultimaConsulta < MIN_ENTRE_CONSULTAS_MS) return
    consultando = true
    ultimaConsulta = Date.now()
    try {
      const v = await versionNueva()
      if (v) {
        detenido = true
        versionDetectada = v
        await esperarLibre()
        alDetectar(v)
      }
    } finally {
      consultando = false
    }
  }

  setInterval(() => revisar(), INTERVALO_MS)
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') revisar() })
  window.addEventListener('focus', () => revisar())
  window.addEventListener('online', () => revisar(true))
  window.addEventListener('pageshow', () => revisar())
  setTimeout(() => revisar(true), 4000)

  return { revisarAhora: () => revisar(true), versionDetectada: () => versionDetectada }
}
