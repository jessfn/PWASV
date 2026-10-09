<template>
  <Teleport to="body">
  <div v-if="show" class="exp-overlay" @click.self="cerrar">
    <div class="exp-modal" role="dialog" aria-modal="true" aria-labelledby="exp-titulo">
      <div class="exp-header">
        <div class="exp-header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="8" y1="13" x2="16" y2="21"/>
            <line x1="16" y1="13" x2="8" y2="21"/>
          </svg>
        </div>
        <div class="exp-header-text">
          <h3 id="exp-titulo">Exportar base a Excel</h3>
          <p>Base completa hasta este momento</p>
        </div>
        <button class="exp-close" @click="cerrar" aria-label="Cerrar">×</button>
      </div>

      <div class="exp-body">
        <!-- Paso 1: elegir -->
        <template v-if="fase === 'config'">
          <p class="exp-label">¿Qué base quieres descargar?</p>
          <div class="exp-options">
            <button type="button" class="exp-option" :class="{ active: tipo === 'actividades' }" @click="tipo = 'actividades'">
              <span class="exp-option-title">Actividades</span>
              <span class="exp-option-sub">Registros de campo y gabinete</span>
            </button>
            <button type="button" class="exp-option" :class="{ active: tipo === 'asistencias' }" @click="tipo = 'asistencias'">
              <span class="exp-option-title">Asistencias</span>
              <span class="exp-option-sub">Entradas y salidas</span>
            </button>
          </div>

          <label class="exp-check">
            <input type="checkbox" v-model="usarRango" />
            <span>Limitar por fechas (por defecto se exporta todo)</span>
          </label>
          <div v-if="usarRango" class="exp-dates">
            <label>Desde<input type="date" v-model="fechaInicio" :max="fechaFin || hoy" /></label>
            <label>Hasta<input type="date" v-model="fechaFin" :min="fechaInicio" :max="hoy" /></label>
          </div>

          <ul class="exp-notes">
            <li>Incluye usuario, cargo y territorio, coordenadas y la URL de cada foto.</li>
            <li>Si hay más de 999,995 registros, el Excel los reparte en varias hojas.</li>
            <li>Una base grande puede tardar varios minutos en prepararse.</li>
            <li>Contiene datos personales: úsalo con cuidado.</li>
          </ul>
        </template>

        <!-- Paso 2: procesando -->
        <template v-else-if="fase === 'procesando'">
          <p class="exp-label">Preparando el Excel de {{ tipo }}…</p>
          <div class="exp-progress"><div class="exp-progress-bar" :style="{ width: porcentaje + '%' }"></div></div>
          <div class="exp-progress-info">
            <span>{{ procesadas.toLocaleString('es-MX') }} de {{ total ? total.toLocaleString('es-MX') : '…' }} registros</span>
            <strong>{{ porcentaje }}%</strong>
          </div>
          <p class="exp-hint">Puedes cerrar esta ventana: la exportación sigue en el servidor. Si la cierras, vuelve a abrirla y elige la misma base para ver el avance.</p>
        </template>

        <!-- Paso 3: listo -->
        <template v-else-if="fase === 'listo'">
          <div class="exp-ok">
            <div class="exp-ok-check">✓</div>
            <h4>Tu Excel está listo</h4>
            <p>
              {{ procesadas.toLocaleString('es-MX') }} registros
              <template v-if="hojas > 1"> en {{ hojas }} hojas</template>
              <template v-if="tamano"> · {{ tamano }}</template>
            </p>
          </div>
          <p class="exp-hint">El enlace de descarga dura unos minutos. Si vence, genera la exportación de nuevo.</p>
        </template>

        <!-- Error -->
        <template v-else-if="fase === 'error'">
          <div class="exp-error">
            <strong>No se pudo completar la exportación</strong>
            <p>{{ errorMsg }}</p>
          </div>
        </template>
      </div>

      <div class="exp-footer">
        <button v-if="fase === 'config'" class="btn-sec" @click="cerrar">Cancelar</button>
        <button v-if="fase === 'config'" class="btn-main" :disabled="!puedeIniciar" @click="iniciar">Generar Excel</button>

        <button v-if="fase === 'procesando'" class="btn-sec" @click="cerrar">Cerrar</button>

        <button v-if="fase === 'listo'" class="btn-sec" @click="reiniciar">Otra base</button>
        <button v-if="fase === 'listo'" class="btn-main" @click="descargar">Descargar Excel</button>

        <button v-if="fase === 'error'" class="btn-sec" @click="cerrar">Cerrar</button>
        <button v-if="fase === 'error'" class="btn-main" @click="reiniciar">Reintentar</button>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import exportarBaseService from '../services/exportarBaseService.js'

const props = defineProps({ show: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const tipo = ref('actividades')
const usarRango = ref(false)
const fechaInicio = ref('')
const fechaFin = ref('')
const fase = ref('config') // config | procesando | listo | error
const procesadas = ref(0)
const total = ref(0)
const hojas = ref(1)
const bytes = ref(0)
const errorMsg = ref('')
const urlRelativa = ref('')

let temporizador = null
let jobActual = null

const hoy = new Date().toISOString().slice(0, 10)

const porcentaje = computed(() => {
  if (!total.value) return 0
  return Math.min(100, Math.floor((procesadas.value / total.value) * 100))
})

const tamano = computed(() => {
  if (!bytes.value) return ''
  const mb = bytes.value / (1024 * 1024)
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes.value / 1024))} KB`
})

const puedeIniciar = computed(() => {
  if (!usarRango.value) return true
  if (!fechaInicio.value && !fechaFin.value) return false
  return !(fechaInicio.value && fechaFin.value && fechaInicio.value > fechaFin.value)
})

function detener() {
  if (temporizador) { clearInterval(temporizador); temporizador = null }
}

function reiniciar() {
  detener()
  jobActual = null
  fase.value = 'config'
  procesadas.value = 0
  total.value = 0
  hojas.value = 1
  bytes.value = 0
  errorMsg.value = ''
  urlRelativa.value = ''
}

function cerrar() {
  detener()
  emit('close')
}

async function consultar() {
  if (!jobActual) return
  try {
    const e = await exportarBaseService.estado(jobActual)
    procesadas.value = e.procesadas || 0
    total.value = e.total || total.value
    if (e.estado === 'listo') {
      detener()
      hojas.value = e.hojas || 1
      bytes.value = e.bytes || 0
      urlRelativa.value = e.descarga_url
      fase.value = 'listo'
    } else if (e.estado === 'error') {
      detener()
      errorMsg.value = e.error || 'Error desconocido en el servidor.'
      fase.value = 'error'
    }
  } catch (err) {
    detener()
    errorMsg.value = err.message
    fase.value = 'error'
  }
}

async function iniciar() {
  const filtros = {}
  if (usarRango.value) {
    if (fechaInicio.value) filtros.fecha_inicio = fechaInicio.value
    if (fechaFin.value) filtros.fecha_fin = fechaFin.value
  }
  try {
    fase.value = 'procesando'
    procesadas.value = 0
    total.value = 0
    const r = await exportarBaseService.iniciar(tipo.value, filtros)
    jobActual = r.job_id
    await consultar()
    if (fase.value === 'procesando') temporizador = setInterval(consultar, 2000)
  } catch (err) {
    errorMsg.value = err.message
    fase.value = 'error'
  }
}

function descargar() {
  if (!urlRelativa.value) return
  // El servidor entrega el archivo con Content-Disposition: el navegador lo baja en streaming.
  window.location.href = exportarBaseService.urlDescarga(urlRelativa.value)
}

watch(() => props.show, (visible) => {
  if (!visible) detener()
})

onBeforeUnmount(detener)
</script>

<style scoped>
.exp-overlay {
  position: fixed; inset: 0; z-index: 10050;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}
.exp-modal {
  width: 100%; max-width: 480px; max-height: 92vh; overflow-y: auto;
  background: #fff; border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  font-family: 'Inter', sans-serif;
}
.exp-header {
  display: flex; align-items: center; gap: 12px; padding: 18px 20px;
  background: linear-gradient(135deg, #1f6f43 0%, #2e8b57 100%); color: #fff;
}
.exp-header-icon {
  width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
  background: rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center;
}
.exp-header-icon svg { width: 22px; height: 22px; }
.exp-header-text { flex: 1; min-width: 0; }
.exp-header-text h3 { margin: 0; font-size: 17px; font-weight: 700; }
.exp-header-text p { margin: 2px 0 0; font-size: 12px; opacity: 0.85; }
.exp-close {
  background: rgba(255, 255, 255, 0.18); border: 0; color: #fff; width: 32px; height: 32px;
  border-radius: 50%; font-size: 22px; line-height: 1; cursor: pointer;
}
.exp-body { padding: 20px; }
.exp-label { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #14492d; }
.exp-options { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.exp-option {
  text-align: left; padding: 12px; border-radius: 12px; cursor: pointer;
  border: 2px solid #d9e4dd; background: #f7faf8; display: flex; flex-direction: column; gap: 4px;
  transition: border-color .15s, background .15s;
}
.exp-option.active { border-color: #1f6f43; background: #e6f2ea; }
.exp-option-title { font-size: 15px; font-weight: 700; color: #14492d; }
.exp-option-sub { font-size: 11.5px; color: #5b6e63; }
.exp-check { display: flex; gap: 8px; align-items: center; font-size: 13px; color: #374151; margin-bottom: 10px; }
.exp-dates { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.exp-dates label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #4b5563; }
.exp-dates input { padding: 8px; border: 1px solid #c9d6ce; border-radius: 8px; font-size: 14px; }
.exp-notes { margin: 8px 0 0; padding-left: 18px; font-size: 12px; color: #6b7c72; line-height: 1.5; }
.exp-progress { height: 12px; background: #e5ece7; border-radius: 999px; overflow: hidden; }
.exp-progress-bar { height: 100%; background: linear-gradient(90deg, #1f6f43, #3fa36b); transition: width .4s ease; }
.exp-progress-info { display: flex; justify-content: space-between; margin-top: 8px; font-size: 13px; color: #374151; }
.exp-hint { margin: 14px 0 0; font-size: 12px; color: #6b7c72; line-height: 1.45; }
.exp-ok { text-align: center; padding: 6px 0 2px; }
.exp-ok-check {
  width: 54px; height: 54px; margin: 0 auto 10px; border-radius: 50%; background: #e6f2ea;
  color: #1f6f43; font-size: 30px; display: flex; align-items: center; justify-content: center; font-weight: 700;
}
.exp-ok h4 { margin: 0 0 4px; font-size: 17px; color: #14492d; }
.exp-ok p { margin: 0; font-size: 13px; color: #4b5563; }
.exp-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 10px; padding: 12px 14px; font-size: 13px; }
.exp-error p { margin: 6px 0 0; word-break: break-word; }
.exp-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px 18px; border-top: 1px solid #eef2ef; }
.btn-main, .btn-sec { padding: 10px 18px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; border: 0; }
.btn-main { background: #1f6f43; color: #fff; }
.btn-main:disabled { opacity: .45; cursor: not-allowed; }
.btn-sec { background: #eef2ef; color: #374151; }
@media (max-width: 480px) {
  .exp-options, .exp-dates { grid-template-columns: 1fr; }
  .exp-footer .btn-main, .exp-footer .btn-sec { flex: 1; }
}
</style>
