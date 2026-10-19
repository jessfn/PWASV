<template>
  <div class="doc" :class="'doc--' + tipo.clave">
    <div class="doc__ico" :style="{ background: tipo.fondo, color: tipo.color }" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" /><path d="M14 3v5h5" /></svg>
      <b>{{ tipo.corto }}</b>
    </div>

    <div class="doc__info">
      <strong>{{ tipo.etiqueta }}</strong>
      <span>{{ detalle }}</span>
    </div>

    <div class="doc__acc">
      <button type="button" class="doc__btn doc__btn--abrir" :disabled="ocupado" @click="abrir">
        <svg v-if="!ocupado" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><path d="M15 3h6v6" /><path d="M10 14L21 3" /></svg>
        <i v-else class="doc__spin" aria-hidden="true"></i>
        {{ ocupado && accion === 'abrir' ? (avance ? avance + '%' : 'Abriendo…') : 'Abrir' }}
      </button>
      <button type="button" class="doc__btn" :disabled="ocupado" @click="guardar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" /></svg>
        {{ ocupado && accion === 'guardar' ? (avance ? avance + '%' : 'Guardando…') : 'Guardar' }}
      </button>
    </div>

    <p v-if="mensaje" class="doc__msg" :class="{ 'is-error': error }" role="status">{{ mensaje }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { tipoDocumento, tamanoLegible, tamanoRemoto, bajarArchivo, guardarBlob, nombreDescarga, puedeCompartirArchivo, compartirArchivo, abrirEnVisor } from '../utils/documentos.js'

const props = defineProps({
  url: { type: String, required: true },          // dirección del archivo (sin parámetros)
  tipoArchivo: { type: String, default: '' },     // columna archivo_tipo del servidor
  nombre: { type: String, default: '' },          // solo para nombrar la descarga; no se muestra
  titulo: { type: String, default: '' },
})

const tipo = computed(() => tipoDocumento(props.tipoArchivo, props.nombre))
const bytes = ref(0)
const ocupado = ref(false)
const accion = ref('')
const avance = ref(0)
const mensaje = ref('')
const error = ref(false)
const detalle = computed(() => tamanoLegible(bytes.value) || 'Toca Abrir para verlo')

const avisar = (txt, esError = false) => { mensaje.value = txt; error.value = esError }
const nombreFinal = () => nombreDescarga(props.nombre || props.titulo, tipo.value, 'documento')

async function obtener() {
  avance.value = 0
  return bajarArchivo(props.url, tipo.value, (n) => { avance.value = n })
}

async function abrir() {
  if (ocupado.value) return
  ocupado.value = true; accion.value = 'abrir'; avisar('')
  try {
    const blob = await obtener()
    const nombre = nombreFinal()
    if (tipo.value.clave === 'pdf' || tipo.value.clave === 'texto') {
      // El visor propio del dispositivo muestra el PDF (en iPhone y Android se abre a pantalla completa)
      if (!abrirEnVisor(blob)) { guardarBlob(blob, nombre); avisar('Se guardó en tus descargas.') }
    } else if (puedeCompartirArchivo(blob, nombre)) {
      // Word, Excel, PowerPoint…: el teléfono ofrece "Abrir con…" y las apps que lo entienden
      try { await compartirArchivo(blob, nombre, props.titulo) } catch (e) { if (e && e.name !== 'AbortError') throw e }
    } else {
      guardarBlob(blob, nombre)
      avisar('Se guardó en tus descargas. Ábrelo desde ahí con tu app de Office.')
    }
  } catch {
    avisar('No se pudo abrir. Revisa tu conexión e inténtalo de nuevo.', true)
  } finally {
    ocupado.value = false; accion.value = ''; avance.value = 0
  }
}

async function guardar() {
  if (ocupado.value) return
  ocupado.value = true; accion.value = 'guardar'; avisar('')
  try {
    const blob = await obtener()
    guardarBlob(blob, nombreFinal())
    avisar('Guardado en tu dispositivo.')
  } catch {
    avisar('No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.', true)
  } finally {
    ocupado.value = false; accion.value = ''; avance.value = 0
  }
}

onMounted(async () => { bytes.value = await tamanoRemoto(props.url) })
</script>

<style scoped>
.doc {
  display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px 14px; align-items: center;
  padding: 14px; border-radius: 18px; background: #fff; border: 1px solid #dbe3ea; box-shadow: 0 10px 26px -20px rgba(15, 23, 42, 0.45);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif;
}
.doc__ico { position: relative; width: 56px; height: 64px; border-radius: 14px; display: grid; place-items: center; }
.doc__ico svg { width: 38px; height: 38px; opacity: 0.35; }
.doc__ico b { position: absolute; bottom: 9px; font-size: 0.66rem; font-weight: 800; letter-spacing: 0.04em; }
.doc__info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.doc__info strong { font-size: 0.95rem; font-weight: 650; color: #0f172a; letter-spacing: -0.01em; }
.doc__info span { font-size: 0.8rem; color: #5b6676; }
.doc__acc { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.doc__btn {
  height: 42px; border: 1px solid #cfd9e1; border-radius: 12px; background: #fff; color: #1e293b; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  font: 650 0.9rem -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif;
  transition: transform 0.15s, background 0.2s; -webkit-tap-highlight-color: transparent;
}
.doc__btn svg { width: 19px; height: 19px; }
.doc__btn:active:not(:disabled) { transform: scale(0.97); }
.doc__btn:disabled { opacity: 0.6; cursor: default; }
.doc__btn--abrir { background: #1d6fe0; border-color: #1d6fe0; color: #fff; }
.doc__spin { width: 16px; height: 16px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff; animation: doc-giro 0.8s linear infinite; }
@keyframes doc-giro { to { transform: rotate(360deg); } }
.doc__msg { grid-column: 1 / -1; margin: 0; font-size: 0.82rem; color: #14532d; font-weight: 600; text-align: center; }
.doc__msg.is-error { color: #b42318; }
@media (min-width: 560px) {
  .doc { grid-template-columns: 56px minmax(0, 1fr) auto; }
  .doc__acc { grid-column: auto; grid-template-columns: auto auto; }
  .doc__btn { padding: 0 18px; }
}
</style>
