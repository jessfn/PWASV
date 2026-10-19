// Avisos push desde el panel: estado de los dispositivos, entrega de cada notificación y reenvíos.
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

const pushService = {
  /** {dispositivos, usuarios_con_push, usuarios_total, ios, android, enviados_7d, fallidos_7d, disponible} */
  async resumen() {
    return manejar(await fetch(`${API_URL}/admin/push/resumen`, { headers: cabeceras() }))
  },

  /** {"<usuario_id>": {dispositivos, ultima_vez, plataformas}} solo de usuarios con push activo */
  async usuarios() {
    return manejar(await fetch(`${API_URL}/admin/push/usuarios`, { headers: cabeceras() }))
  },

  /** Cómo salió el push de una notificación (entregados, fallidos, usuarios sin push). */
  async deNotificacion(id) {
    return manejar(await fetch(`${API_URL}/admin/push/notificacion/${id}`, { headers: cabeceras() }))
  },

  /** Vuelve a mandar el push solo a quienes aún no leyeron la notificación. */
  async reenviar(id) {
    return manejar(await fetch(`${API_URL}/admin/push/reenviar/${id}`, { method: 'POST', headers: cabeceras() }))
  },

  /** Aviso de prueba a los dispositivos de un usuario. */
  async probar(usuarioId) {
    return manejar(await fetch(`${API_URL}/admin/push/prueba/${usuarioId}`, { method: 'POST', headers: cabeceras() }))
  }
}

export default pushService
