// "Enterado" de notificaciones, con cola sin conexión:
// si no hay internet al tocar el botón, se guarda en el teléfono y se envía solo al recuperar la señal.
import notificacionesService from '../services/notificacionesService.js'

const CLAVE = 'enterados_pendientes'

const leerCola = () => {
  try { return JSON.parse(localStorage.getItem(CLAVE) || '[]') } catch { return [] }
}
const guardarCola = (c) => {
  try { localStorage.setItem(CLAVE, JSON.stringify(c)) } catch { /* sin almacenamiento */ }
}

/** Ids de notificaciones marcadas sin conexión que aún no llegan al servidor (para mostrarlas ya como enterado). */
export const enteradosPendientes = () => new Set(leerCola().map((e) => e.id))

async function enviar(id, usuarioId) {
  return notificacionesService.marcarEnterado(id, usuarioId, `browser_${navigator.platform || 'web'}`)
}

/**
 * Marca "Enterado". Devuelve {ok, offline, enterado_en}.
 * Respuesta inmediata aunque no haya internet: queda en cola y se sincroniza después.
 */
export async function marcarEnterado(id, usuarioId) {
  const ahora = new Date().toISOString()
  if (!navigator.onLine) {
    const c = leerCola()
    if (!c.some((e) => e.id === id)) { c.push({ id, usuarioId, t: ahora }); guardarCola(c) }
    return { ok: true, offline: true, enterado_en: ahora }
  }
  try {
    const r = await enviar(id, usuarioId)
    return { ok: true, offline: false, enterado_en: (r && r.enterado_en) || ahora }
  } catch (e) {
    if (e && e.response && e.response.status >= 400 && e.response.status < 500) return { ok: false, offline: false }
    const c = leerCola() // falla de red o del servidor: se guarda para reintentar
    if (!c.some((x) => x.id === id)) { c.push({ id, usuarioId, t: ahora }); guardarCola(c) }
    return { ok: true, offline: true, enterado_en: ahora }
  }
}

/** Envía lo que quedó en cola. Devuelve cuántos se enviaron. */
export async function sincronizarEnterados() {
  const c = leerCola()
  if (!c.length || !navigator.onLine) return 0
  const restantes = []
  let enviados = 0
  for (const e of c) {
    try { await enviar(e.id, e.usuarioId); enviados++ } catch (err) {
      if (!(err && err.response && err.response.status >= 400 && err.response.status < 500)) restantes.push(e)
    }
  }
  guardarCola(restantes)
  return enviados
}
