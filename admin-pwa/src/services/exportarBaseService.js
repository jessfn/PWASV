// Servicio para exportar la base completa (actividades o asistencias) a Excel.
// Flujo: iniciar() -> estado() cada pocos segundos -> descargar con la URL firmada que devuelve el servidor.
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
  if (res.status === 403) throw new Error('No tienes permiso para exportar esta base.')
  throw new Error(detalle || `Error ${res.status}`)
}

const exportarBaseService = {
  /**
   * Inicia la generación del Excel en el servidor.
   * @param {'actividades'|'asistencias'} tipo
   * @param {{fecha_inicio?: string, fecha_fin?: string}} filtros  (AAAA-MM-DD, opcionales)
   */
  async iniciar(tipo, filtros = {}) {
    const res = await fetch(`${API_URL}/admin/exportar-base/${tipo}`, {
      method: 'POST',
      headers: cabeceras(),
      body: JSON.stringify(filtros)
    })
    return manejar(res)
  },

  async estado(jobId) {
    const res = await fetch(`${API_URL}/admin/exportar-base/estado/${jobId}`, { headers: cabeceras() })
    return manejar(res)
  },

  /** Convierte la ruta relativa firmada del servidor en URL absoluta de descarga. */
  urlDescarga(rutaRelativa) {
    return `${API_URL}${rutaRelativa}`
  }
}

export default exportarBaseService
