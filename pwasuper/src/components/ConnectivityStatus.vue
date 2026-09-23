<template>
  <!--
    Franja de estado de conectividad.
    Se renderiza EN LÍNEA dentro del header verde (parte del mismo bloque),
    no como una barra flotante independiente.
  -->
  <div
    v-if="showBanner"
    class="cs-strip"
    :class="stateClass"
    role="status"
    aria-live="polite"
    @click="pendientes.total > 0 && openModal()"
  >
    <div class="cs-strip__left">
      <span class="cs-strip__icon" aria-hidden="true">
        <!-- Sin conexión -->
        <svg v-if="!isOnline" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 2l20 20M8.5 16.4a5 5 0 017 0M12 20h.01M5 12.9a10 10 0 015.2-2.7M19 12.9a10 10 0 00-2.4-1.9M1.4 9a15 15 0 015.3-3.2M22.6 9a15 15 0 00-6.4-3.6" />
        </svg>
        <!-- Sincronizando -->
        <span v-else-if="isSyncing" class="cs-spin"></span>
        <!-- Conectado -->
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0M12 20h.01" />
        </svg>
      </span>

      <div class="cs-strip__text">
        <p class="cs-strip__title">{{ bannerTitle }}</p>
        <p v-if="bannerSubtitle" class="cs-strip__sub">{{ bannerSubtitle }}</p>
      </div>
    </div>

    <div class="cs-strip__right">
      <button
        v-if="pendientes.total > 0"
        type="button"
        class="cs-strip__pill"
        @click.stop="openModal"
      >
        Detalles
      </button>
      <div class="cs-strip__clock">
        <span class="cs-strip__time">{{ horaActual }}</span>
        <span class="cs-strip__date">{{ fechaActual }}</span>
      </div>
    </div>
  </div>

  <teleport to="body">
    <!-- Modal de detalle cuando hay pendientes -->
    <div
      v-if="props.show && showModal && pendientes.total > 0"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      @click="closeModal"
    >
      <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" @click.stop>
        <div class="text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full mb-4" :class="modalIconClasses">
            <svg v-if="!isOnline" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m2.829 2.829L18 18M8.464 15.536a5 5 0 010-7.072m0 0l2.829 2.829m-2.829-2.829L6 6M5.636 18.364a9 9 0 010-12.728m0 0l2.829 2.829m-2.829-2.829L3 3" />
            </svg>
            <div v-else-if="isSyncing" class="animate-spin rounded-full h-6 w-6 border-b-2 border-current"></div>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>

          <h3 class="text-lg font-medium text-gray-900 mb-2">{{ modalTitle }}</h3>
          <p class="text-sm text-gray-500 mb-4">{{ modalMessage }}</p>

          <div v-if="isSyncing && syncProgress" class="mb-4">
            <div class="bg-gray-200 rounded-full h-2">
              <div
                class="bg-blue-700 h-2 rounded-full transition-all duration-300"
                :style="{ width: `${(syncProgress.procesados / syncProgress.total) * 100}%` }"
              ></div>
            </div>
            <p class="text-xs text-gray-500 mt-1">
              {{ syncProgress.procesados }} / {{ syncProgress.total }}
              ({{ syncProgress.exitosos }} exitosos, {{ syncProgress.fallidos }} fallidos)
            </p>
          </div>

          <div class="flex gap-3 justify-center">
            <button
              @click="closeModal"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cerrar
            </button>
            <button
              v-if="isOnline && !isSyncing && pendientes.total > 0"
              @click="sincronizarManual"
              class="px-4 py-2 text-sm font-medium text-white bg-blue-700 rounded-lg hover:bg-blue-800 transition-colors"
            >
              Sincronizar ahora
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Aviso flotante mínimo (solo si la franja del header está oculta) -->
    <div
      v-if="props.show && !showBanner && !isOnline && !bannerDismissed"
      class="fixed bottom-4 right-4 z-50 bg-red-700 text-white p-3 rounded-lg shadow-lg flex items-center max-w-sm"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <div class="text-sm">
        <div>Sin conexión</div>
        <div v-if="pendientes.total > 0" class="text-xs mt-1">
          {{ pendientes.total }} elemento{{ pendientes.total > 1 ? 's' : '' }} pendiente{{ pendientes.total > 1 ? 's' : '' }}
          <span class="opacity-80">({{ pendientes.registros }} reg, {{ pendientes.asistencias }} asist)</span>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import syncService from '../services/syncService.js';
import { checkInternetConnection } from '../utils/network.js';

const props = defineProps({
  show: {
    type: Boolean,
    default: true
  }
});

// Estado reactivo
const isOnline = ref(true);
const isSyncing = ref(false);
const pendientes = ref({ registros: 0, asistencias: 0, total: 0 });
const syncProgress = ref(null);
const showModal = ref(false);
const bannerDismissed = ref(false);
const lastSyncResult = ref(null);
const lastConnectionCheck = ref(Date.now());

// Un solo "tick" por segundo alimenta el reloj y el "verificado hace…"
const now = ref(Date.now());
const horaActual = ref('');
const fechaActual = ref('');

const HORA_OPTS = { timeZone: 'America/Mexico_City', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
const FECHA_OPTS = { timeZone: 'America/Mexico_City', day: '2-digit', month: '2-digit', year: 'numeric' };

const timeAgoText = computed(() => {
  const secs = Math.floor((now.value - lastConnectionCheck.value) / 1000);
  if (secs < 2) return 'ahora';
  if (secs < 60) return `hace ${secs}s`;
  if (secs < 3600) return `hace ${Math.floor(secs / 60)}m`;
  return `hace ${Math.floor(secs / 3600)}h`;
});

const showBanner = computed(() => props.show);

const stateClass = computed(() => {
  if (!isOnline.value) return 'cs-strip--offline';
  if (isSyncing.value) return 'cs-strip--syncing';
  if (pendientes.value.total > 0) return 'cs-strip--pending';
  return 'cs-strip--online';
});

const modalIconClasses = computed(() => {
  if (!isOnline.value) return 'bg-red-100 text-red-700';
  if (isSyncing.value) return 'bg-blue-100 text-blue-700';
  return 'bg-green-100 text-green-700';
});

const plural = (n, s, p) => (n === 1 ? s : p);

const bannerTitle = computed(() => {
  const t = pendientes.value.total;
  if (!isOnline.value) return 'Sin conexión';
  if (isSyncing.value) return 'Sincronizando...';
  if (t > 0) return `${t} ${plural(t, 'registro pendiente', 'registros pendientes')}`;
  return 'Conectado';
});

const bannerSubtitle = computed(() => {
  const { registros, asistencias, total } = pendientes.value;
  const check = `Verificado ${timeAgoText.value}`;
  if (!isOnline.value && total > 0) return `${registros} reg, ${asistencias} asist. se enviarán al reconectar`;
  if (isSyncing.value && syncProgress.value) return `${syncProgress.value.procesados}/${syncProgress.value.total} procesados`;
  if (total > 0) return `${registros} reg, ${asistencias} asist. · Toca para sincronizar`;
  if (!isOnline.value) return check;
  return check;
});

const modalTitle = computed(() => {
  if (!isOnline.value) return 'Sin conexión a internet';
  if (isSyncing.value) return 'Sincronizando registros';
  if (lastSyncResult.value) return 'Sincronización completada';
  return 'Registros pendientes';
});

const modalMessage = computed(() => {
  const { registros, asistencias, total } = pendientes.value;
  const detalle = `(${registros} ${plural(registros, 'registro', 'registros')}, ${asistencias} ${plural(asistencias, 'asistencia', 'asistencias')})`;
  if (!isOnline.value) {
    return `Tienes ${total} ${plural(total, 'elemento guardado', 'elementos guardados')} ${detalle} que se enviarán automáticamente cuando recuperes la conexión.`;
  }
  if (isSyncing.value) return 'Enviando tus registros y asistencias guardados al servidor...';
  if (lastSyncResult.value) {
    const { exitosos, fallidos } = lastSyncResult.value;
    return `Se enviaron ${exitosos} ${plural(exitosos, 'elemento', 'elementos')} correctamente${fallidos > 0 ? ` y ${fallidos} fallaron` : ''}.`;
  }
  return `Tienes ${total} ${plural(total, 'elemento pendiente', 'elementos pendientes')} de envío ${detalle}.`;
});

// Controles
const openModal = () => {
  showModal.value = true;
  bannerDismissed.value = true;
};

const closeModal = () => {
  showModal.value = false;
  lastSyncResult.value = null;
  syncProgress.value = null;
};

const sincronizarManual = async () => {
  try {
    await syncService.sincronizarManual();
  } catch (error) {
    console.error('Error en sincronización manual:', error);
  }
};

// Eventos de sincronización
const handleSyncEvent = (event, online, data) => {
  isOnline.value = online;

  switch (event) {
    case 'online':
    case 'offline':
      bannerDismissed.value = false;
      break;

    case 'syncing':
      isSyncing.value = true;
      syncProgress.value = null;
      bannerDismissed.value = false;
      break;

    case 'sync_progress':
      syncProgress.value = data;
      break;

    case 'sync_complete':
      isSyncing.value = false;
      lastSyncResult.value = data;
      syncProgress.value = null;
      actualizarPendientes().then(() => {
        if (data.exitosos > 0 && data.fallidos === 0) {
          setTimeout(() => {
            bannerDismissed.value = true;
            showModal.value = false;
          }, 3000);
        }
      });
      break;

    case 'sync_error':
      isSyncing.value = false;
      syncProgress.value = null;
      actualizarPendientes();
      break;
  }
};

const actualizarPendientes = async () => {
  try {
    const nuevos = await syncService.obtenerPendientes(true);
    // Solo reasignar si algo cambió: evita re-renders innecesarios cada 5s
    const p = pendientes.value;
    if (nuevos.total !== p.total || nuevos.registros !== p.registros || nuevos.asistencias !== p.asistencias) {
      pendientes.value = nuevos;
    }
    return nuevos;
  } catch (error) {
    console.error('Error obteniendo pendientes:', error);
    return null;
  }
};

const tickReloj = () => {
  const d = new Date();
  now.value = d.getTime();
  horaActual.value = d.toLocaleTimeString('es-MX', HORA_OPTS);
  fechaActual.value = d.toLocaleDateString('es-MX', FECHA_OPTS);
};

// Evita verificaciones solapadas
let verificandoConectividad = false;
const verificarConectividad = async () => {
  if (verificandoConectividad) return;
  verificandoConectividad = true;
  try {
    const nuevaConexion = await checkInternetConnection();
    lastConnectionCheck.value = Date.now();
    if (isOnline.value !== nuevaConexion) {
      isOnline.value = nuevaConexion;
    }
  } catch (error) {
    console.error('Error verificando conectividad:', error);
  } finally {
    verificandoConectividad = false;
  }
};

let pendientesInterval = null;
let conectividadInterval = null;
let relojInterval = null;

// Los hooks de desmontaje deben registrarse de forma síncrona en el setup.
// (Antes se registraban dentro de un onMounted async y nunca se ejecutaban,
// dejando los intervalos corriendo para siempre.)
onUnmounted(() => {
  clearInterval(pendientesInterval);
  clearInterval(conectividadInterval);
  clearInterval(relojInterval);
  syncService.removeListener(handleSyncEvent);
});

onMounted(async () => {
  syncService.addListener(handleSyncEvent);

  const status = syncService.getConnectionStatus();
  isOnline.value = status.isOnline;
  isSyncing.value = status.isSyncing;

  tickReloj();
  relojInterval = setInterval(tickReloj, 1000);

  await actualizarPendientes();
  pendientesInterval = setInterval(actualizarPendientes, 5000);

  await verificarConectividad();
  conectividadInterval = setInterval(verificarConectividad, 20000);
});
</script>

<style scoped>
/* ===== Franja de estado, unida al header ===== */
.cs-strip {
  --cs-bg-a: #2f8f3a;
  --cs-bg-b: #55a52b;
  --cs-fg: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 12px 6px 10px;
  color: var(--cs-fg);
  background: linear-gradient(90deg, var(--cs-bg-a), var(--cs-bg-b));
  /* línea de luz fina que "suelda" la franja con la barra verde de arriba */
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
  transition: background 0.35s ease, color 0.35s ease;
  font-size: 10.5px;
  line-height: 1.15;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.cs-strip--offline  { --cs-bg-a: #dc2626; --cs-bg-b: #b91c1c; }
.cs-strip--syncing  { --cs-bg-a: #0284c7; --cs-bg-b: #0369a1; }
.cs-strip--pending  { --cs-bg-a: #f59e0b; --cs-bg-b: #d97706; --cs-fg: #3b2a00; }

.cs-strip__left {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  flex: 1 1 auto;
}

.cs-strip__icon {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
}
.cs-strip__icon svg { width: 12px; height: 12px; }

.cs-spin {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: cs-rotate 0.8s linear infinite;
}
@keyframes cs-rotate { to { transform: rotate(360deg); } }

.cs-strip__text { min-width: 0; }
.cs-strip__title {
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cs-strip__sub {
  opacity: 0.82;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-strip__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.cs-strip__clock {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-variant-numeric: tabular-nums;
}
.cs-strip__time { font-weight: 700; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.cs-strip__date { opacity: 0.82; }

.cs-strip__pill {
  border: 0;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 10px;
  font-weight: 700;
  color: inherit;
  background: rgba(255, 255, 255, 0.28);
  cursor: pointer;
}
.cs-strip__pill:active { background: rgba(255, 255, 255, 0.4); }

@media (max-width: 340px) {
  .cs-strip__sub { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .cs-spin { animation-duration: 2s; }
}
</style>
