<template>
  <section v-if="visible" class="po" :class="'po--' + estado" aria-live="polite">
    <span class="po__ico" aria-hidden="true">
      <svg v-if="estado === 'activo'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 01-3.4 0" /><path d="M9 11l2 2 4-4" /></svg>
      <svg v-else-if="estado === 'denegado'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.7 21a2 2 0 01-3.4 0" /><path d="M18.6 13A17 17 0 0118 8a6 6 0 00-9.3-5" /><path d="M6.3 6.3A6 6 0 006 8c0 7-3 9-3 9h14" /><path d="M3 3l18 18" /></svg>
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 01-3.4 0" /></svg>
    </span>

    <div class="po__txt">
      <template v-if="estado === 'activo'">
        <h3>Avisos en tu teléfono: activados</h3>
        <p>Te llegarán al instante, aunque la app esté cerrada.</p>
      </template>
      <template v-else-if="estado === 'inactivo'">
        <h3>Recibe tus avisos al instante</h3>
        <p>Activa las notificaciones del teléfono y te llegarán aunque la app esté cerrada.</p>
      </template>
      <template v-else-if="estado === 'denegado'">
        <h3>Los avisos están bloqueados</h3>
        <p>Actívalos en los ajustes: toca el candado junto a la dirección (o los ajustes de la app) y permite “Notificaciones”.</p>
      </template>
      <template v-else-if="estado === 'instalar'">
        <h3>Instala la app para recibir avisos</h3>
        <p>En iPhone: toca <b>Compartir</b> y luego <b>Añadir a pantalla de inicio</b>. Abre la app desde su icono y activa los avisos aquí.</p>
      </template>
      <p v-if="mensaje" class="po__msg" :class="{ 'is-error': mensajeError }" role="status">{{ mensaje }}</p>
    </div>

    <div class="po__acc">
      <button v-if="estado === 'inactivo'" type="button" class="po__btn po__btn--on" :disabled="ocupado" @click="activar">
        {{ ocupado ? 'Activando…' : 'Activar avisos' }}
      </button>
      <template v-else-if="estado === 'activo'">
        <button type="button" class="po__btn po__btn--quiet" :disabled="ocupado" @click="apagar">Desactivar</button>
      </template>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { estadoPush, activarPush, desactivarPush } from '../utils/push.js'

// En Notificaciones solo se muestra mientras falta activarlos; ya activos, se administran en Configuración
const props = defineProps({ ocultarActivo: { type: Boolean, default: false } })
const emit = defineEmits(['cambio'])
const exitoReciente = ref(false)
const estado = ref('cargando')
const ocupado = ref(false)
const mensaje = ref('')
const mensajeError = ref(false)

const usuarioId = () => { try { return (JSON.parse(localStorage.getItem('user') || 'null') || {}).id || null } catch { return null } }
const avisar = (txt, error = false) => { mensaje.value = txt; mensajeError.value = error; if (txt) setTimeout(() => { if (mensaje.value === txt) mensaje.value = '' }, 6000) }

const visible = computed(() => {
  if (estado.value === 'no-soportado' || estado.value === 'cargando') return false
  if (props.ocultarActivo && estado.value === 'activo' && !exitoReciente.value) return false
  return true
})

const refrescar = async () => {
  estado.value = (await estadoPush()).estado
  emit('cambio', estado.value)
}

const activar = async () => {
  const id = usuarioId()
  if (!id || ocupado.value) return
  ocupado.value = true
  mensaje.value = ''
  const r = await activarPush(id)
  ocupado.value = false
  if (r.ok) {
    avisar('Listo: ya recibirás tus avisos en el teléfono. Podrás administrarlos en Configuración.')
    exitoReciente.value = true
    setTimeout(() => { exitoReciente.value = false }, 5000)
  }
  else if (r.motivo === 'denegado') avisar('El permiso fue rechazado. Puedes cambiarlo en los ajustes del navegador.', true)
  else if (r.motivo === 'sin-servidor') avisar('El servicio de avisos no está disponible por ahora.', true)
  else if (r.motivo !== 'cerrado') avisar('No se pudo activar. Revisa tu conexión e inténtalo de nuevo.', true)
  await refrescar()
}

const apagar = async () => {
  ocupado.value = true
  await desactivarPush()
  ocupado.value = false
  avisar('Avisos del teléfono desactivados.')
  await refrescar()
}

const alVolver = () => { if (document.visibilityState === 'visible') refrescar() }
onMounted(() => { refrescar(); document.addEventListener('visibilitychange', alVolver) })
onBeforeUnmount(() => document.removeEventListener('visibilitychange', alVolver))
</script>

<style scoped>
.po {
  display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 12px 14px; align-items: start;
  margin: 0 0 14px; padding: 14px 16px; border-radius: 20px;
  background: linear-gradient(135deg, #f1f7ff 0%, #ffffff 70%); border: 1px solid #c9ddf7;
  box-shadow: 0 10px 26px -18px rgba(29, 111, 224, 0.55);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif;
}
.po__ico { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; color: #1d5fc4; background: #e3eefc; }
.po__ico svg { width: 22px; height: 22px; }
.po__txt h3 { margin: 0; font-size: 0.96rem; font-weight: 650; color: #0f172a; letter-spacing: -0.01em; }
.po__txt p { margin: 3px 0 0; font-size: 0.84rem; line-height: 1.4; color: #475467; }
.po__msg { color: #14532d !important; font-weight: 600; }
.po__msg.is-error { color: #b42318 !important; }
.po__acc { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; }
.po__acc:empty { display: none; }
.po__btn {
  height: 38px; padding: 0 16px; border: 1px solid #cfd9e1; border-radius: 12px; background: #fff; color: #1e293b;
  font: 600 0.85rem -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif; cursor: pointer;
  transition: transform 0.15s, background 0.2s; -webkit-tap-highlight-color: transparent;
}
.po__btn:active:not(:disabled) { transform: scale(0.97); }
.po__btn:disabled { opacity: 0.55; cursor: default; }
.po__btn--on { border-color: transparent; background: linear-gradient(135deg, #2f7bf0, #1d5fc4); color: #fff; box-shadow: 0 8px 18px -10px rgba(29, 95, 196, 0.8); }
.po__btn--quiet { border-color: transparent; background: transparent; color: #5b6676; }
.po--activo { background: linear-gradient(135deg, #effaf3 0%, #ffffff 70%); border-color: #b6e3c6; box-shadow: 0 10px 26px -18px rgba(22, 128, 61, 0.55); }
.po--activo .po__ico { background: #d8f2e2; color: #146b35; }
.po--denegado, .po--instalar { background: linear-gradient(135deg, #fff6e5 0%, #ffffff 70%); border-color: #f2d49b; box-shadow: none; }
.po--denegado .po__ico, .po--instalar .po__ico { background: #fdebc8; color: #8a4b00; }
@media (min-width: 640px) {
  .po { grid-template-columns: 44px minmax(0, 1fr) auto; align-items: center; }
  .po__acc { grid-column: auto; justify-content: flex-end; flex-wrap: nowrap; }
}
</style>
