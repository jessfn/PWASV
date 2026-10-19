// Descarga en segundo plano (cuando el teléfono está libre) lo que las pantallas más usadas muestran primero,
// para que la primera vez que se abran también aparezcan al instante.
import notificacionesService from '../services/notificacionesService.js'
import { manualesService } from '../services/manualesService'
import { cacheGuardar } from './cacheVista.js'

export async function precargarDatos() {
  try {
    if (!navigator.onLine) return
    const c = navigator.connection || {}
    if (c.saveData) return
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    if (!user || !user.id) return
    const [n, m] = await Promise.allSettled([
      notificacionesService.obtenerListaNotificaciones(user.id, 'all', 20, 0),
      manualesService.obtenerManualesUsuario(user.id),
    ])
    if (n.status === 'fulfilled' && n.value && n.value.notificaciones && n.value.notificaciones.length) cacheGuardar('notificaciones', n.value.notificaciones.slice(0, 40))
    if (m.status === 'fulfilled' && m.value && m.value.manuales && m.value.manuales.length) cacheGuardar('manuales', m.value.manuales)
  } catch { /* la precarga nunca debe molestar */ }
}
