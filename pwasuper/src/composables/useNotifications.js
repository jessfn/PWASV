import { ref, reactive } from 'vue'
import notificacionesService from '../services/notificacionesService.js'
import { prepararSonido, ding, anunciarNuevas, registrarConocidas, hayLineaBase, activarSonido, sonidoActivado } from '../utils/sonidoNotificacion.js'

// Estado global de notificaciones
const globalNotificationState = reactive({
  unreadCount: 0,
  isLoading: false,
  lastUpdate: null,
  userId: null,
  soundEnabled: true, // NUEVO: Control del sonido
  previousCount: 0,   // NUEVO: Para detectar cambios
  isInitialized: false // NUEVO: Para evitar sonido en carga inicial
})

// Referencia reactiva al conteo no leídas
const unreadCount = ref(0)
const isUpdating = ref(false)

// ===== Sonido: un "ding" por cada notificación NUEVA (por id), nunca por cambios del contador =====
let globalAudioNotification = null
const initializeGlobalAudio = () => { prepararSonido() }

// Cuando el contador sube se pregunta cuáles ids son nuevos; solo suena si alguno no se conocía antes
let revisandoNuevas = false
const revisarNuevas = async (userId) => {
  if (revisandoNuevas || !userId) return
  revisandoNuevas = true
  try {
    const r = await notificacionesService.obtenerListaNotificaciones(userId, 'all', 15, 0)
    const ids = ((r && r.notificaciones) || []).map((n) => n.id)
    if (!hayLineaBase(userId)) registrarConocidas(userId, ids)   // primera vez en este dispositivo: solo aprende
    else anunciarNuevas(userId, ids)
  } catch { /* el siguiente sondeo lo reintenta */ } finally {
    revisandoNuevas = false
  }
}

const playGlobalNotificationSound = () => { ding() }

const detectNewNotifications = (newCount, userId) => {
  if (newCount > globalNotificationState.previousCount) revisarNuevas(userId)
  globalNotificationState.previousCount = newCount
}

// NUEVO: Solicitar permisos de notificación
// El permiso de avisos del teléfono solo se pide desde la tarjeta "Activar avisos" (con un toque de la persona)
const requestNotificationPermission = async () => ('Notification' in window && Notification.permission === 'granted')

/**
 * Composable para manejar el estado global de notificaciones
 * Útil para mostrar badges en iconos de campana, etc.
 */
export const useNotifications = () => {
  
  /**
   * Obtener ID de usuario desde localStorage
   */
  const getUserId = () => {
    try {
      // 1. Buscar en 'user' (formato principal de PWASUPER)
      const userData = localStorage.getItem('user')
      if (userData) {
        const user = JSON.parse(userData)
        const id = user.id || user.usuario_id || user.user_id
        if (id) return parseInt(id)
      }
      
      // 2. Buscar en 'userData' (formato alternativo)
      const alternativeUserData = localStorage.getItem('userData')
      if (alternativeUserData) {
        const user = JSON.parse(alternativeUserData)
        const id = user.id || user.usuario_id || user.user_id
        if (id) return parseInt(id)
      }
      
      // 3. Fallback: buscar IDs directos
      const directIds = ['userId', 'user_id', 'id']
      for (const key of directIds) {
        const id = localStorage.getItem(key)
        if (id) return parseInt(id)
      }
      
      return null
    } catch (error) {
      console.error('Error obteniendo user ID:', error)
      return null
    }
  }

  /**
   * Actualizar conteo de notificaciones no leídas
   */
  const fetchUnreadCount = async (userId = null) => {
    try {
      const currentUserId = userId || getUserId()
      if (!currentUserId) {
        console.warn('No hay usuario identificado para obtener notificaciones')
        return 0
      }

      if (isUpdating.value) {
        console.log('Ya hay una actualización en curso...')
        return globalNotificationState.unreadCount
      }

      isUpdating.value = true
      globalNotificationState.isLoading = true
      globalNotificationState.userId = currentUserId
      
      // Solo hacer log detallado si es la primera vez o si hay cambios
      const isFirstLoad = globalNotificationState.lastUpdate === null
      if (isFirstLoad) {
        console.log(`🔔 Cargando conteo inicial de notificaciones para usuario ${currentUserId}`)
      }
      
      const count = await notificacionesService.obtenerConteoNoLeidas(currentUserId)
      
      // NUEVO: Detectar cambios y reproducir sonido si corresponde
      if (globalNotificationState.isInitialized) {
        detectNewNotifications(count, currentUserId)
      } else {
        // Primera carga - establecer contador base sin sonido y aprender las notificaciones que ya existen
        globalNotificationState.previousCount = count
        globalNotificationState.isInitialized = true
        revisarNuevas(currentUserId)
        console.log(`🔔 Estado inicial establecido: ${count} notificaciones no leídas`)
      }
      
      // Actualizar estado global
      const prevCount = globalNotificationState.unreadCount
      globalNotificationState.unreadCount = count
      globalNotificationState.lastUpdate = new Date()
      unreadCount.value = count
      
      // Solo hacer log si cambió o es la primera carga
      if (isFirstLoad || prevCount !== count) {
        console.log(`🔔 Badge actualizado: ${prevCount || 0} → ${count} notificaciones no leídas`)
      }
      
      return count
      
    } catch (error) {
      console.error('Error obteniendo conteo no leídas:', error)
      
      // En desarrollo, simular datos
      if (import.meta.env.DEV) {
        const simulatedCount = Math.floor(Math.random() * 5)
        globalNotificationState.unreadCount = simulatedCount
        unreadCount.value = simulatedCount
        console.log(`🧪 Modo desarrollo: simulando ${simulatedCount} no leídas`)
        return simulatedCount
      }
      
      return 0
    } finally {
      isUpdating.value = false
      globalNotificationState.isLoading = false
    }
  }

  /**
   * Marcar una notificación como leída y actualizar conteo inmediatamente
   */
  const markAsRead = async (notificationId) => {
    try {
      const userId = getUserId()
      if (!userId) return false

      console.log(`🔔 Marcando notificación ${notificationId} como leída...`)
      
      // Actualización optimista del badge (decrementar inmediatamente)
      if (globalNotificationState.unreadCount > 0) {
        globalNotificationState.unreadCount--
        unreadCount.value = globalNotificationState.unreadCount
        console.log(`🔔 Badge actualizado optimísticamente: ${unreadCount.value}`)
      }

      const deviceId = `browser_${navigator.userAgent.split(' ').pop()}_${Date.now()}`
      
      await notificacionesService.marcarComoLeida(notificationId, userId, deviceId)
      
      // Verificar el conteo real del servidor para confirmar
      await fetchUnreadCount(userId)
      
      console.log(`✅ Notificación ${notificationId} marcada como leída correctamente`)
      return true
      
    } catch (error) {
      console.error('Error marcando como leída:', error)
      
      // Revertir actualización optimista en caso de error
      if (globalNotificationState.unreadCount >= 0) {
        globalNotificationState.unreadCount++
        unreadCount.value = globalNotificationState.unreadCount
        console.log(`🔄 Revirtiendo badge por error: ${unreadCount.value}`)
      }
      
      return false
    }
  }

  /**
   * Inicializar polling automático del conteo - cada segundo para respuesta inmediata
   */
  let sondeoActivo = null
  const startPolling = (intervalMs = 10000) => { // cada 10 s; los avisos push llegan al instante
    const userId = getUserId()
    if (!userId) return null
    if (sondeoActivo) return sondeoActivo   // un solo sondeo: antes se creaban varios y el sonido se repetía

    console.log(`🔄 Iniciando polling global cada ${intervalMs / 1000}s para notificaciones`)
    
    // NUEVO: Inicializar audio global y solicitar permisos
    initializeGlobalAudio()
    // (el permiso de avisos se pide solo desde la tarjeta "Activar avisos", nunca por sorpresa)
    
    // Obtener conteo inicial
    fetchUnreadCount(userId)
    
    // Configurar interval - actualización constante para detectar nuevas notificaciones
    const intervalId = setInterval(async () => {
      if (!isUpdating.value) {
        // Actualización con detección de cambios y sonido
        const prevCount = globalNotificationState.unreadCount
        await fetchUnreadCount(userId)
        
        // Solo hacer log si cambió el conteo
        if (prevCount !== globalNotificationState.unreadCount) {
          console.log(`🔔 Badge actualizado globalmente: ${prevCount} → ${globalNotificationState.unreadCount}`)
        }
      }
    }, intervalMs)
    
    sondeoActivo = intervalId
    return intervalId
  }

  /**
   * Detener polling
   */
  const stopPolling = (intervalId) => {
    if (intervalId) {
      if (intervalId === sondeoActivo) sondeoActivo = null
      clearInterval(intervalId)
      console.log('🔄 Polling de notificaciones detenido')
    }
  }

  /**
   * Reiniciar estado (útil al cambiar de usuario)
   */
  const resetState = () => {
    globalNotificationState.unreadCount = 0
    globalNotificationState.isLoading = false
    globalNotificationState.lastUpdate = null
    globalNotificationState.userId = null
    globalNotificationState.previousCount = 0 // NUEVO: Reiniciar contador anterior
    globalNotificationState.isInitialized = false // NUEVO: Reiniciar inicialización
    unreadCount.value = 0
    isUpdating.value = false
    
    console.log('🔄 Estado de notificaciones reiniciado')
  }

  /**
   * Obtener información de estado completa
   */
  const getState = () => {
    return {
      unreadCount: globalNotificationState.unreadCount,
      isLoading: globalNotificationState.isLoading,
      lastUpdate: globalNotificationState.lastUpdate,
      userId: globalNotificationState.userId,
      isUpdating: isUpdating.value,
      soundEnabled: globalNotificationState.soundEnabled, // NUEVO
      previousCount: globalNotificationState.previousCount, // NUEVO
      isInitialized: globalNotificationState.isInitialized // NUEVO
    }
  }

  // NUEVO: Controlar sonido
  const enableSound = () => {
    globalNotificationState.soundEnabled = true
    console.log('🔊 Sonido de notificaciones habilitado')
  }

  const disableSound = () => {
    globalNotificationState.soundEnabled = false
    console.log('🔇 Sonido de notificaciones deshabilitado')
  }

  // NUEVO: Reproducir sonido manualmente (para pruebas)
  const playTestSound = () => {
    playGlobalNotificationSound()
  }

  return {
    // Estado reactivo
    unreadCount,
    isUpdating,
    
    // Métodos existentes
    fetchUnreadCount,
    markAsRead,
    startPolling,
    stopPolling,
    resetState,
    getState,
    getUserId,
    
    // NUEVOS: Métodos de sonido
    enableSound,
    disableSound,
    playTestSound,
    requestNotificationPermission,
    initializeGlobalAudio,
    
    // Estado global (solo lectura)
    state: globalNotificationState
  }
}

export default useNotifications
