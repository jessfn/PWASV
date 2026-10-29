<template>
  <div class="vr-page">
    <main class="vr-card">
      <header class="vr-logos">
        <img :src="logoBienestar" alt="Bienestar" class="vr-logo" />
        <img :src="logoSV" alt="Sembrando Vida" class="vr-logo" />
      </header>
      <div class="vr-line"></div>

      <p class="vr-eyebrow">Verificación de reporte</p>
      <p class="vr-folio">{{ folio }}</p>

      <div v-if="estado === 'cargando'" class="vr-estado"><span class="vr-spin"></span>Consultando…</div>

      <template v-else-if="estado === 'valido'">
        <div class="vr-ok">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          {{ datos.detalle ? 'Folio auténtico · datos originales' : 'Folio auténtico' }}
        </div>
        <dl class="vr-datos">
          <div><dt>Prestador de servicios</dt><dd>{{ datos.prestador || '—' }}</dd></div>
          <div><dt>Periodo</dt><dd>{{ datos.mes }} {{ datos.anio }}</dd></div>
          <div><dt>Estado</dt><dd>{{ datos.firmado ? 'Firmado por el responsable' : 'Pendiente de firma' }}</dd></div>
          <div v-if="datos.firmado && datos.fecha_firma"><dt>Fecha de firma</dt><dd>{{ fechaFirma }}</dd></div>
        </dl>

        <template v-if="datos.detalle">
          <div class="vr-stats">
            <div class="vr-stat"><b>{{ datos.total }}</b><small>Actividades</small></div>
            <div class="vr-stat"><b>{{ datos.campo }}</b><small>Campo</small></div>
            <div class="vr-stat"><b>{{ datos.gabinete }}</b><small>Gabinete</small></div>
          </div>
          <h3 class="vr-h3">Actividades registradas</h3>
          <div v-for="(a, i) in datos.actividades" :key="i" class="vr-act">
            <span class="vr-n">{{ i + 1 }}</span>
            <div>
              <p><span class="vr-tag" :class="{ g: a.tipo === 'gabinete' }">{{ a.tipo === 'gabinete' ? 'GABINETE' : 'CAMPO' }}</span>{{ a.descripcion || 'Sin descripción' }}</p>
              <small>{{ fechaActividad(a.fecha_hora) }}</small>
            </div>
          </div>
          <div class="vr-hash">Huella de integridad del reporte<b>{{ datos.huella }}</b>Debe coincidir con la impresa en el PDF.</div>
          <p class="vr-aviso">Compara esta lista con el documento que tienes en mano. Si hay actividades de más, de menos o distintas, el documento fue alterado.</p>
        </template>
        <p v-else class="vr-nota">Para ver el contenido original del reporte, escanea el código QR impreso en el documento.</p>
      </template>

      <template v-else-if="estado === 'invalido'">
        <div class="vr-bad">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          Folio no encontrado
        </div>
        <p class="vr-nota">Este folio no corresponde a ningún reporte registrado. Verifica que esté escrito igual que en el documento.</p>
      </template>

      <p v-else class="vr-nota">No se pudo consultar en este momento. Intenta de nuevo más tarde.</p>

      <p class="vr-pie">Secretaría de Bienestar · Sembrando Vida</p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import logoBienestar from '../assets/images/logo-bienestar.png'
import logoSV from '../assets/images/logo-sembrando-vida.png'
import { apiService } from '../services/apiService.js'

const route = useRoute()
const folio = computed(() => String(route.params.folio || '').toUpperCase())
const estado = ref('cargando')
const datos = ref({})
const fechaActividad = (f) => {
  try {
    const d = new Date(f)
    return d.toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) + ' · ' + d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch (e) { return '' }
}
const fechaFirma = computed(() => {
  try { return new Date(datos.value.fecha_firma).toLocaleDateString('es-MX', { day: '2-digit', month: 'long', year: 'numeric' }) } catch (e) { return '' }
})

onMounted(async () => {
  try {
    const base = (apiService.getCurrentApiUrl && apiService.getCurrentApiUrl()) || 'https://apipwa.sembrandodatos.com'
    const r = await fetch(`${base}/reportes/verificar-folio/${encodeURIComponent(folio.value)}?c=${encodeURIComponent(String(route.query.c || ''))}`)
    if (!r.ok) throw new Error('http ' + r.status)
    const j = await r.json()
    if (j && j.valido) { datos.value = j; estado.value = 'valido' } else { estado.value = 'invalido' }
  } catch (e) {
    estado.value = 'error'
  }
})
</script>

<style scoped>
.vr-page { position: fixed; inset: 0; z-index: 9999; overflow: auto; background: #f5f2ee; display: flex; align-items: flex-start; justify-content: center; padding: 28px 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
.vr-card { width: 100%; max-width: 440px; background: #fff; border-radius: 18px; padding: 22px 22px 18px; box-shadow: 0 10px 40px rgba(60, 20, 30, .12); text-align: center; color: #1f2937; }
.vr-logos { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.vr-logo { height: 34px; width: auto; max-width: 46%; object-fit: contain; }
.vr-line { height: 3px; margin: 14px 0 0; background: #611232; border-radius: 2px; position: relative; }
.vr-line::after { content: ''; position: absolute; left: 0; right: 0; bottom: -5px; height: 1px; background: #c9a227; }
.vr-eyebrow { margin: 24px 0 4px; font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: #6b7280; font-weight: 700; }
.vr-folio { margin: 0 0 18px; font-size: 1.5rem; font-weight: 800; color: #611232; letter-spacing: .02em; font-variant-numeric: tabular-nums; }
.vr-ok, .vr-bad { display: inline-flex; align-items: center; gap: 8px; padding: 9px 16px; border-radius: 999px; font-weight: 700; font-size: .95rem; }
.vr-ok { background: #e7f6ec; color: #17653a; }
.vr-bad { background: #fdecec; color: #a12626; }
.vr-ok svg, .vr-bad svg { width: 18px; height: 18px; }
.vr-datos { margin: 20px 0 4px; text-align: left; border-top: 1px solid #ece7e1; }
.vr-datos > div { padding: 12px 2px; border-bottom: 1px solid #ece7e1; }
.vr-datos dt { font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; color: #7a8190; font-weight: 700; }
.vr-datos dd { margin: 3px 0 0; font-size: .98rem; font-weight: 600; }
.vr-nota { margin: 16px 4px 4px; font-size: .9rem; color: #5b6472; line-height: 1.45; }
.vr-estado { display: inline-flex; align-items: center; gap: 10px; color: #6b7280; font-weight: 600; }
.vr-spin { width: 16px; height: 16px; border-radius: 50%; border: 2px solid #d9d2cb; border-top-color: #611232; animation: vr-giro .8s linear infinite; }
@keyframes vr-giro { to { transform: rotate(360deg); } }
.vr-pie { margin: 22px 0 0; font-size: .72rem; color: #9aa1ad; }

.vr-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 16px 0 4px; }
.vr-stat { background: #faf6f4; border: 1px solid #eadfe3; border-radius: 12px; padding: 10px 6px; }
.vr-stat b { display: block; font-size: 1.3rem; color: #611232; }
.vr-stat small { font-size: .65rem; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }
.vr-h3 { margin: 18px 0 6px; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: #611232; text-align: left; }
.vr-act { display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid #f0ebe6; text-align: left; }
.vr-n { flex: none; width: 22px; height: 22px; border-radius: 50%; background: #f3e6ea; color: #611232; font-size: .7rem; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.vr-act p { margin: 0; font-size: .82rem; line-height: 1.35; }
.vr-act small { display: block; color: #7a8190; font-size: .7rem; margin-top: 2px; }
.vr-tag { display: inline-block; font-size: .6rem; font-weight: 700; padding: 1px 7px; border-radius: 99px; color: #fff; background: #2f7d4f; margin-right: 6px; vertical-align: 1px; }
.vr-tag.g { background: #6b4a8f; }
.vr-hash { margin-top: 16px; background: #f6f3f0; border-radius: 12px; padding: 10px 12px; font-size: .7rem; color: #5b6472; line-height: 1.4; }
.vr-hash b { display: block; font-family: ui-monospace, Menlo, monospace; color: #1f2937; font-size: .8rem; margin-top: 2px; letter-spacing: .04em; }
.vr-aviso { margin: 14px 4px 0; font-size: .74rem; color: #7a8190; line-height: 1.4; }
</style>
