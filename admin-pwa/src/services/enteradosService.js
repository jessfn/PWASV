// "Enterado" de notificaciones: resumen por persona, recordatorio y Excel (panel administrador).
import { API_URL } from '../config/api.js'

const cabeceras = () => ({
  'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`,
  'Content-Type': 'application/json'
})

async function manejar(res) {
  if (res.ok) return res.json()
  let detalle = ''
  try { detalle = (await res.json()).detail } catch (e) { /* sin cuerpo JSON */ }
  if (res.status === 401) throw new Error('Tu sesión expiró. Inicia sesión nuevamente.')
  throw new Error(detalle || `Error ${res.status}`)
}

const enteradosService = {
  /** {resumen:{destinatarios,enterados,vieron,sin_leer,pct_*}, usuarios:[...], total_filtrados} */
  async obtener(id, { estado = 'enterado', q = '', limit = 50, offset = 0 } = {}) {
    const p = new URLSearchParams({ estado, q, limit, offset })
    return manejar(await fetch(`${API_URL}/admin/notificaciones/${id}/enterados?${p}`, { headers: cabeceras() }))
  },

  /** Push de recordatorio solo a quienes aún no marcan "Enterado". */
  async recordar(id) {
    return manejar(await fetch(`${API_URL}/admin/notificaciones/${id}/recordar`, { method: 'POST', headers: cabeceras() }))
  },

  /** Descarga el Excel con el detalle por persona. */
  async descargarExcel(id) {
    const res = await fetch(`${API_URL}/admin/notificaciones/${id}/enterados/excel`, { headers: cabeceras() })
    if (!res.ok) {
      let detalle = ''
      try { detalle = (await res.json()).detail } catch (e) { /* sin cuerpo */ }
      throw new Error(detalle || `Error ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Enterados_${id}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  }
}

export default enteradosService
