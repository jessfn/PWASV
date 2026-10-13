<template>
  <div class="root">

    <!-- ══════════════════════════════════════
         PANEL IZQUIERDO — naturaleza sin personas
         ══════════════════════════════════════ -->
    <aside class="left-panel" aria-hidden="true">
      <div class="left-overlay"></div>

      <!-- Contenido encima de la imagen -->
      <div class="left-body">
        <!-- Badge institucional -->
        <div class="badge">
          <span class="badge-dot"></span>
          Sistema Oficial de Seguimiento
        </div>

        <!-- Título grande -->
        <h1 class="left-heading">
          Sembrando<br>
          <span class="left-heading-accent">Vida</span>
        </h1>

        <p class="left-desc">
          Subsecretaría de Inclusión Productiva<br>y Desarrollo Rural
        </p>

        <!-- Separador -->
        <div class="left-sep"></div>

        <!-- Stats / pilares -->
        <div class="pillars">
          <div class="pillar">
            <span class="pillar-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
            </span>
            <div class="pillar-text">Geolocalización<br>en tiempo real</div>
          </div>
          <div class="pillar">
            <span class="pillar-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </span>
            <div class="pillar-text">Registro de<br>asistencias</div>
          </div>
          <div class="pillar">
            <span class="pillar-ico">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <line x1="1" y1="6" x2="23" y2="6"/>
                <line x1="1" y1="10" x2="17" y2="10"/>
                <line x1="1" y1="14" x2="11" y2="14"/>
                <line x1="1" y1="18" x2="7" y2="18"/>
              </svg>
            </span>
            <div class="pillar-text">Modo<br>sin conexión</div>
          </div>
        </div>
      </div>

      <!-- Círculos decorativos -->
      <div class="deco d1"></div>
      <div class="deco d2"></div>
      <div class="deco d3"></div>
    </aside>

    <!-- ══════════════════════════════════════
         PANEL DERECHO — formulario
         ══════════════════════════════════════ -->
    <main class="right-panel">
      <div class="form-card">

        <!-- Marca -->
        <div class="brand rise" style="--d: 0s">
          <img src="/images/logosv.webp" width="768" height="512" decoding="async" alt="Sembrando Vida" class="brand-logo" />
        </div>

        <!-- Encabezado -->
        <header class="form-header rise" style="--d: .06s">
          <span class="app-pill">Aplicación de Seguimiento</span>
          <h2 class="form-title">Iniciar sesión</h2>
        </header>

        <!-- Aviso: contraseña actualizada desde la liga del correo -->
        <transition name="pop">
          <div v-if="resetOk" class="note note-ok" role="status">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
            <span>Tu contraseña se actualizó. Inicia sesión con la nueva.</span>
          </div>
        </transition>

        <!-- Error -->
        <transition name="pop">
          <div v-if="errorMessage" class="note note-error" role="alert" aria-live="assertive">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ errorMessage }}</span>
          </div>
        </transition>

        <form @submit.prevent="login" novalidate class="form" :class="{ shake: sacudir }">

          <!-- Correo -->
          <div class="field rise" style="--d: .12s" :class="{ invalid: correoInvalido, filled: email }">
            <span class="field-ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="3"/><path d="m2 7 10 6 10-6"/></svg>
            </span>
            <input
              ref="emailInput"
              v-model.trim="email"
              id="email"
              type="email"
              inputmode="email"
              autocomplete="username"
              autocapitalize="none"
              spellcheck="false"
              placeholder=" "
              required
              :disabled="loading"
              @blur="correoTocado = true"
              @keydown.enter.prevent="irAContrasena"
              class="inp"
            />
            <label for="email" class="float-label">Correo electrónico</label>
          </div>
          <p v-if="correoInvalido" class="hint hint-error">Escribe un correo válido, por ejemplo nombre@correo.com</p>

          <!-- Contraseña -->
          <div class="field rise" style="--d: .18s" :class="{ invalid: formError && !password, filled: password }">
            <span class="field-ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="3"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>
            </span>
            <input
              ref="passwordInput"
              v-model="password"
              id="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder=" "
              required
              :disabled="loading"
              @keyup="detectarMayusculas"
              @keydown="detectarMayusculas"
              class="inp inp-pass"
            />
            <label for="password" class="float-label">Contraseña</label>
            <button type="button" class="eye" @click="togglePasswordVisibility" :disabled="loading" :aria-label="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'" :aria-pressed="showPassword">
              <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>

          <div v-if="mayusculas" class="row-aux">
            <span class="caps" role="status">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 4 13h4v5h8v-5h4z"/></svg>
              Bloq Mayús activado
            </span>
          </div>

          <button type="submit" class="btn-submit rise" style="--d: .26s" :disabled="loading">
            <span v-if="loading" class="spinner" aria-hidden="true"></span>
            <span class="btn-text">{{ loading ? 'Verificando…' : 'Iniciar sesión' }}</span>
            <svg v-if="!loading" class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg>
          </button>
        </form>

        <div class="sep rise" style="--d: .30s" aria-hidden="true"></div>

        <p class="signup rise" style="--d: .32s">¿No tienes cuenta? <router-link to="/register" class="link-strong">Crear cuenta</router-link></p>

        <router-link to="/forgot-password" class="link-soft forgot rise" style="--d: .34s">¿Olvidaste tu contraseña?</router-link>

        <p class="copy rise" style="--d: .36s">© 2026 Sembrando Vida · Todos los derechos reservados</p>

      </div><!-- /form-card -->
    </main>

    <SupportBubbleLogin />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import axios from 'axios';
import { API_URL } from '../utils/network.js';
import SupportBubbleLogin from '../components/SupportBubbleLogin.vue';
import { enviarInfoDispositivo } from '../services/dispositivoTrackingService.js';

const router = useRouter();
const route = useRoute();
const resetOk = ref(route.query.reset === 'ok');
const email = ref('');
const password = ref('');
const showPassword = ref(false);
const loading = ref(false);
const errorMessage = ref('');
const formError = ref(false);
const MAX_RETRIES = 2;

const sacudir = ref(false);
const correoTocado = ref(false);
const mayusculas = ref(false);
const emailInput = ref(null);
const passwordInput = ref(null);

const correoMalFormado = computed(() => !!email.value && !/^\S+@\S+\.\S+$/.test(email.value));
const correoInvalido = computed(() => (correoTocado.value && correoMalFormado.value) || (formError.value && (!email.value || correoMalFormado.value)));

function sacudirFormulario() {
  sacudir.value = false;
  requestAnimationFrame(() => {
    sacudir.value = true;
    setTimeout(() => { sacudir.value = false; }, 480);
  });
}

function detectarMayusculas(e) {
  mayusculas.value = !!(e.getModifierState && e.getModifierState('CapsLock'));
}

function irAContrasena() {
  if (!password.value && passwordInput.value) passwordInput.value.focus();
  else login();
}

const META_TEMA = ['meta[name="theme-color"]'];
const coloresTema = [];

onMounted(() => {
  // Fondo y barra de estado verdes mientras se ve el acceso (sin franjas claras al final de la página)
  document.documentElement.classList.add('login-bg');
  document.querySelectorAll(META_TEMA[0]).forEach((m) => { coloresTema.push([m, m.getAttribute('content')]); m.setAttribute('content', '#0b3d24'); });

  // Recuerda el último correo usado y coloca el cursor donde toca (sin abrir el teclado en celulares)
  try {
    const ultimo = localStorage.getItem('login_email');
    if (ultimo && !email.value) email.value = ultimo;
  } catch { /* almacenamiento no disponible */ }
  if (window.matchMedia && window.matchMedia('(pointer: fine)').matches) {
    (email.value ? passwordInput.value : emailInput.value)?.focus();
  }
});

function togglePasswordVisibility() { showPassword.value = !showPassword.value; }

onBeforeUnmount(() => {
  document.documentElement.classList.remove('login-bg');
  coloresTema.forEach(([m, c]) => m.setAttribute('content', c));
});

async function intentarLogin(correo, contrasena) {
  const r = await axios.post(`${API_URL}/login`, { correo, contrasena }, {
    timeout: 30000, headers: { 'Content-Type': 'application/json' }
  });
  return r.data;
}

async function login() {
  if (!email.value || !password.value) {
    errorMessage.value = 'Por favor completa todos los campos';
    formError.value = true;
    sacudirFormulario();
    return;
  }
  if (correoMalFormado.value) {
    errorMessage.value = 'Escribe un correo electrónico válido';
    formError.value = true;
    sacudirFormulario();
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  formError.value = false;

  for (let i = 0; i <= MAX_RETRIES; i++) {
    if (i > 0) {
      errorMessage.value = `Reintentando conexión (${i}/${MAX_RETRIES})...`;
      await new Promise(r => setTimeout(r, 3000 * i));
    }
    try {
      const data = await intentarLogin(email.value, password.value);
      localStorage.setItem('user', JSON.stringify(data));
      try { localStorage.setItem('login_email', email.value); } catch { /* opcional */ }
      enviarInfoDispositivo(data.id).catch(() => {});
      sessionStorage.setItem('justLoggedIn', 'true');
      window.location.href = '/';
      return;
    } catch (err) {
      if (err.response) {
        const s = err.response.status;
        errorMessage.value = s === 401 ? 'Credenciales incorrectas. Verifica tu email y contraseña.'
          : s === 403 ? (err.response.data?.detail || 'Cuenta desactivada. Contacta al administrador.')
          : s === 500 ? 'Error del servidor. Inténtalo en unos minutos.'
          : (err.response.data?.detail || 'Error al iniciar sesión.');
        formError.value = true;
        loading.value = false;
        sacudirFormulario();
        return;
      }
    }
  }
  formError.value = true;
  sacudirFormulario();
  loading.value = false;
  errorMessage.value = !navigator.onLine
    ? 'Sin conexión a internet.'
    : 'No se pudo conectar con el servidor. Intenta de nuevo.';
}
</script>

<style scoped>

/* ── reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ════════════════════════════════════════
   RAÍZ — flex horizontal
   ════════════════════════════════════════ */
.root {
  display: flex;
  align-items: stretch;   /* paneles estiran al alto real del contenido */
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  color-scheme: light only;
}

/* ════════════════════════════════════════
   PANEL IZQUIERDO
   ════════════════════════════════════════ */
.left-panel {
  display: none; /* oculto en móvil */
  position: relative;
  overflow: hidden;
  background:
    url('https://images.unsplash.com/photo-1523348837708-15d4a09cfac2?auto=format&fit=crop&w=1400&q=90')
    center/cover no-repeat;
}

/* Filtro verde profundo + degradado lateral */
.left-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(to right, rgba(2,44,18,0.15) 0%, rgba(2,44,18,0.08) 100%),
    linear-gradient(170deg,
      rgba(2,44,18,0.93)   0%,
      rgba(10,68,30,0.86) 30%,
      rgba(20,100,50,0.78) 60%,
      rgba(34,160,74,0.62) 100%
    );
  z-index: 1;
}

/* Contenido izquierdo — flex column, distribuye el espacio disponible */
.left-body {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  /* Padding escala con vh igual que el panel derecho */
  padding: clamp(28px, 5vh, 64px) clamp(24px, 4vw, 56px);
  color: #fff;
  overflow: hidden;
}

/* Badge */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
  backdrop-filter: blur(8px);
  border-radius: 100px;
  padding: clamp(4px, 0.7vh, 6px) clamp(10px, 1.5vw, 16px);
  font-size: clamp(10px, 1.3vh, 12px);
  font-weight: 600;
  letter-spacing: 0.4px;
  color: rgba(255,255,255,0.9);
  width: fit-content;
  margin-bottom: clamp(14px, 3vh, 36px);
  flex-shrink: 0;
}
.badge-dot {
  width: clamp(5px, 0.8vh, 7px);
  height: clamp(5px, 0.8vh, 7px);
  background: #4ade80;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(74,222,128,0.8);
  animation: blink 2s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Título — escala con vh */
.left-heading {
  font-size: clamp(28px, 6.5vh, 68px);
  font-weight: 900;
  line-height: 1.0;
  letter-spacing: clamp(-1px, -0.2vw, -2px);
  color: #fff;
  margin-bottom: clamp(8px, 1.8vh, 20px);
  text-shadow: 0 4px 30px rgba(0,0,0,0.25);
  flex-shrink: 0;
}
.left-heading-accent {
  background: linear-gradient(135deg, #4ade80 0%, #bbf7d0 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.left-desc {
  font-size: clamp(11px, 1.5vh, 14px);
  color: rgba(255,255,255,0.65);
  line-height: 1.6;
  margin-bottom: clamp(12px, 2.5vh, 36px);
  flex-shrink: 0;
}

/* Separador */
.left-sep {
  width: 48px;
  height: 3px;
  background: linear-gradient(90deg, #4ade80, transparent);
  border-radius: 99px;
  margin-bottom: clamp(12px, 2.5vh, 36px);
  flex-shrink: 0;
}

/* Pilares */
.pillars {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.4vh, 16px);
  flex-shrink: 0;
}
.pillar {
  display: flex;
  align-items: center;
  gap: clamp(10px, 1.5vw, 16px);
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(6px);
  border-radius: clamp(10px, 1.5vh, 14px);
  padding: clamp(8px, 1.5vh, 14px) clamp(12px, 1.8vw, 18px);
  transition: background 0.2s;
}
.pillar:hover { background: rgba(255,255,255,0.12); }
.pillar-ico {
  display: flex; align-items: center; justify-content: center;
  width: clamp(28px, 4.5vh, 38px);
  height: clamp(28px, 4.5vh, 38px);
  flex-shrink: 0;
  background: rgba(74,222,128,0.15);
  border: 1px solid rgba(74,222,128,0.25);
  border-radius: clamp(7px, 1.2vh, 10px);
  color: #4ade80;
}
.pillar-ico svg { width: clamp(14px, 2.2vh, 18px); height: clamp(14px, 2.2vh, 18px); }
.pillar-text {
  font-size: clamp(10px, 1.4vh, 13px);
  color: rgba(255,255,255,0.88);
  font-weight: 500;
  line-height: 1.4;
}

/* Círculos decorativos */
.deco {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.07);
  z-index: 1;
  pointer-events: none;
}
.d1 { width: 380px; height: 380px; top: -120px; right: -120px; background: rgba(255,255,255,0.03); animation: spin-slow 40s linear infinite; }
.d2 { width: 240px; height: 240px; bottom: -60px; left: -60px;  background: rgba(74,222,128,0.04); animation: spin-slow 30s linear infinite reverse; }
.d3 { width: 140px; height: 140px; bottom: 20%;  right: 8%;     background: rgba(255,255,255,0.04); animation: spin-slow 25s linear infinite; }
@keyframes spin-slow { to { transform: rotate(360deg); } }

/* ════════════════════════════════════════
   PANEL DERECHO — sin scroll, todo encaja
   ════════════════════════════════════════ */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  overflow: hidden;
  padding: clamp(10px, 2.5vw, 36px);
  position: relative;
  background: linear-gradient(145deg, #052e16 0%, #14532d 40%, #166534 70%, #15803d 100%);
}

.right-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 60% 50% at 20% 20%, rgba(74,222,128,0.15) 0%, transparent 60%),
    radial-gradient(ellipse 50% 60% at 85% 80%, rgba(21,128,61,0.22) 0%, transparent 55%);
  pointer-events: none;
  z-index: 0;
}

/* ════════════════════════════════════════
   TARJETA DE ACCESO — liquid glass, compacta y fluida
   ════════════════════════════════════════ */
.right-panel {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.form-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 372px;
  margin: auto;
  display: flex;
  flex-direction: column;
  padding: clamp(18px, 3vh, 26px) clamp(20px, 2.6vw, 28px) clamp(14px, 2.2vh, 20px);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  isolation: isolate;
  overflow: hidden;

  /* Vidrio líquido: poco blanco, mucho desenfoque y brillo de borde */
  background:
    linear-gradient(135deg, rgba(255,255,255,0.82) 0%, rgba(255,255,255,0.68) 55%, rgba(255,255,255,0.74) 100%);
  -webkit-backdrop-filter: blur(16px) saturate(1.5);
  backdrop-filter: blur(16px) saturate(1.5);
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 30px;
  box-shadow:
    inset 0 1.5px 0 rgba(255, 255, 255, 0.85),
    inset 0 -1px 0 rgba(255, 255, 255, 0.25),
    inset 0 0 28px rgba(255, 255, 255, 0.12),
    0 26px 60px -16px rgba(0, 0, 0, 0.45),
    0 8px 20px -8px rgba(0, 0, 0, 0.22);
}
/* brillo especular en la esquina superior */
.form-card::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(120% 70% at 12% -10%, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0) 55%),
    radial-gradient(90% 60% at 100% 110%, rgba(134,239,172,0.14) 0%, rgba(134,239,172,0) 60%);
}

/* La tarjeta NO se anima (el desenfoque costoso no se recalcula): solo sus bloques internos */
.rise { animation: rise 0.55s cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: var(--d, 0s); }
@keyframes rise {
  from { opacity: 0; transform: translate3d(0, 10px, 0); }
  to   { opacity: 1; transform: translate3d(0, 0, 0); }
}

/* Marca */
.brand { text-align: center; line-height: 0; overflow: hidden; height: clamp(76px, 11.5vh, 104px); flex-shrink: 0; }
.brand-logo { height: clamp(117px, 17.7vh, 160px); width: auto; max-width: 100%; object-fit: cover; object-position: top; display: block; margin: 0 auto; filter: drop-shadow(0 3px 8px rgba(21,128,61,0.22)); }

/* Encabezado: píldora verde + título */
.form-header { display: flex; flex-direction: column; align-items: center; margin: clamp(6px, 1.2vh, 10px) 0 clamp(12px, 2vh, 16px); }
.app-pill {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 6px 15px;
  border-radius: 999px;
  font-size: 12.5px; font-weight: 650; letter-spacing: 0.01em; line-height: 1;
  color: #ffffff;
  background: linear-gradient(135deg, #22b455 0%, #15803d 100%);
  box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 8px 16px -8px rgba(21,128,61,0.7);
}
.form-title {
  position: relative;
  margin-top: 12px;
  padding-bottom: 7px;
  font-size: 16.5px;
  font-weight: 700;
  letter-spacing: -0.005em;
  line-height: 1.15;
  color: #15803d; /* respaldo si el navegador no soporta el degradado en texto */
  background: linear-gradient(90deg, #166534 0%, #22c55e 45%, #166534 100%);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: brillo 3.6s linear infinite;
}
/* subrayado que se dibuja al entrar */
.form-title::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 34px;
  height: 3px;
  border-radius: 3px;
  background: linear-gradient(90deg, #22c55e, #15803d);
  transform: translateX(-50%) scaleX(0);
  transform-origin: center;
  animation: subrayado 0.7s 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
@keyframes brillo { to { background-position: -220% 0; } }
@keyframes subrayado { to { transform: translateX(-50%) scaleX(1); } }

/* Avisos */
.note { display: flex; align-items: flex-start; gap: 9px; padding: 10px 12px; margin-bottom: 12px; border-radius: 14px; font-size: 13px; line-height: 1.4; font-weight: 500; }
.note svg { width: 17px; height: 17px; flex-shrink: 0; margin-top: 1px; }
.note-ok { background: rgba(236,253,243,0.92); color: #166534; border: 1px solid #bbf7d0; }
.note-error { background: rgba(255,241,242,0.94); color: #be123c; border: 1px solid #fecdd3; }
.pop-enter-active, .pop-leave-active { transition: opacity 0.24s ease, transform 0.24s cubic-bezier(0.22, 1, 0.36, 1); }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-6px); }

/* Formulario */
.form { display: flex; flex-direction: column; }
.form.shake { animation: shake 0.42s cubic-bezier(0.36, 0.07, 0.19, 0.97); }
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(3px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-5px, 0, 0); }
  40%, 60% { transform: translate3d(5px, 0, 0); }
}

/* Campo con etiqueta flotante */
.field { position: relative; margin-bottom: 10px; }
.inp {
  width: 100%;
  height: 52px;
  padding: 20px 44px 5px 44px;
  font: inherit;
  font-size: 15.5px;
  color: #08170f;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  outline: none;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) inset;
  transition: background 0.18s, border-color 0.18s, box-shadow 0.18s;
}
.inp::placeholder { color: transparent; }
.inp:hover:not(:disabled) { background: #ffffff; }
.inp:focus {
  background: #ffffff;
  border-color: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.18);
}
.inp:disabled { opacity: 0.6; }

.float-label {
  position: absolute;
  left: 44px;
  top: 50%;
  transform: translate3d(0, -50%, 0);
  font-size: 15.5px;
  color: #3f5247;
  pointer-events: none;
  transition: top 0.16s ease, transform 0.16s ease, color 0.16s ease, font-size 0.16s ease;
}
.inp:focus + .float-label,
.inp:not(:placeholder-shown) + .float-label {
  top: 15px;
  font-size: 11.5px;
  color: #15803d;
  font-weight: 650;
}

.field-ico { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); width: 19px; height: 19px; color: #44564b; transition: color 0.18s; pointer-events: none; }
.field-ico svg { width: 100%; height: 100%; }
.field:focus-within .field-ico { color: #16a34a; }

.field.invalid .inp { border-color: #f43f5e; background: rgba(255, 247, 248, 0.92); }
.field.invalid .inp:focus { box-shadow: 0 0 0 4px rgba(244, 63, 94, 0.14); }
.field.invalid .float-label { color: #be123c; }

.eye {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  width: 44px; height: 44px; display: grid; place-items: center;
  border: 0; border-radius: 13px; background: transparent; color: #3f5247; cursor: pointer;
  transition: background 0.18s, color 0.18s;
  -webkit-tap-highlight-color: transparent;
}
.eye svg { width: 19px; height: 19px; }
.eye:hover:not(:disabled) { background: rgba(22,163,74,0.12); color: #15803d; }

.hint { margin: -3px 4px 9px; font-size: 12px; }
.hint-error { color: #be123c; }

/* Aviso de Bloq Mayús */
.row-aux { display: flex; align-items: center; min-height: 20px; margin: 0 4px 10px; }
.caps { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 650; color: #b45309; }
.caps svg { width: 13px; height: 13px; }

/* Botón principal */
.btn-submit {
  position: relative;
  display: flex; align-items: center; justify-content: center; gap: 9px;
  width: 100%; height: 50px; margin-top: 4px;
  border: 0; border-radius: 16px;
  font: inherit; font-size: 16px; font-weight: 650; letter-spacing: -0.01em;
  color: #ffffff; cursor: pointer;
  background: linear-gradient(180deg, #22b455 0%, #15803d 100%);
  box-shadow:
    0 1px 0 rgba(255,255,255,0.4) inset,
    0 12px 22px -10px rgba(21, 128, 61, 0.7),
    0 3px 8px -3px rgba(21, 128, 61, 0.4);
  transition: transform 0.16s ease, box-shadow 0.2s, filter 0.2s;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}
.btn-submit:hover:not(:disabled) { transform: translate3d(0, -2px, 0); filter: brightness(1.05); }
.btn-submit:hover:not(:disabled) .btn-arrow { transform: translate3d(3px, 0, 0); }
.btn-submit:active:not(:disabled) { transform: scale(0.98); }
.btn-submit:focus-visible { outline: 3px solid rgba(22,163,74,0.4); outline-offset: 3px; }
.btn-submit:disabled { cursor: progress; filter: saturate(0.85); }
.btn-arrow { width: 19px; height: 19px; transition: transform 0.18s; }
.spinner { width: 19px; height: 19px; border-radius: 50%; border: 2.5px solid rgba(255,255,255,0.4); border-top-color: #fff; animation: giro 0.75s linear infinite; }
@keyframes giro { to { transform: rotate(360deg); } }

/* Pie de la tarjeta: separador, crear cuenta y olvidé contraseña */
.sep { height: 1px; margin: clamp(12px, 2vh, 16px) 8% 0; background: linear-gradient(90deg, transparent, rgba(22,101,52,0.32), transparent); }
.signup { text-align: center; margin-top: clamp(10px, 1.6vh, 14px); font-size: 13.5px; font-weight: 500; color: #1f3328; }
.link-strong { color: #15803d; font-weight: 700; text-decoration: none; margin-left: 4px; }
.link-strong:hover { text-decoration: underline; text-underline-offset: 3px; }
.forgot { align-self: center; margin-top: 6px; padding: 8px 10px; }
.link-soft { font-size: 13.5px; font-weight: 650; color: #15803d; text-decoration: none; border-radius: 10px; -webkit-tap-highlight-color: transparent; }
.link-soft:hover { color: #0f5132; text-decoration: underline; text-underline-offset: 3px; }
.copy { text-align: center; margin-top: 4px; font-size: 11px; color: #2f4a3a; }

@media (prefers-reduced-motion: reduce) {
  .rise, .form.shake, .spinner, .form-title { animation: none !important; }
  .form-title::after { animation: none !important; transform: translateX(-50%) scaleX(1); }
  .pop-enter-active, .pop-leave-active, .btn-submit, .inp, .float-label { transition: none !important; }
}

/* ════════════════════════════════════════
   DESKTOP ≥ 1024px — split-screen
   ════════════════════════════════════════ */
@media (min-width: 1024px) {
  .root { height: 100vh; overflow: hidden; }
  .left-panel { display: flex; width: 54%; flex-shrink: 0; height: 100vh; overflow: hidden; }
  .right-panel { width: 46%; }
}
@media (min-width: 1280px) {
  .left-panel { width: 56%; }
  .right-panel { width: 44%; }
}

/* ════════════════════════════════════════
   TABLET 768–1023px
   ════════════════════════════════════════ */
@media (min-width: 768px) and (max-width: 1023px) {
  .root { height: 100dvh; overflow: hidden; }
  .right-panel { height: 100dvh; }
}

/* ════════════════════════════════════════
   MÓVIL < 768px — ligero: menos desenfoque, sin animaciones pesadas
   ════════════════════════════════════════ */
@media (max-width: 767px) {
  .root { height: auto; min-height: 100dvh; overflow: visible; }
  .right-panel {
    height: auto;
    min-height: 100dvh;
    padding: max(16px, env(safe-area-inset-top)) 16px max(16px, env(safe-area-inset-bottom));
    background:
      linear-gradient(160deg, rgba(2,44,18,0.90) 0%, rgba(10,68,30,0.82) 45%, rgba(21,128,61,0.78) 100%),
      url('https://images.unsplash.com/photo-1523348837708-15d4a09cfac2?auto=format&fit=crop&w=640&q=60') center/cover no-repeat;
  }
  .form-card {
    max-width: 360px;
    border-radius: 28px;
    padding: 20px 20px 14px;
    /* menos blur = mucho más fluido en gamas bajas */
    -webkit-backdrop-filter: blur(10px) saturate(1.4);
    backdrop-filter: blur(10px) saturate(1.4);
  }
  .brand { height: clamp(72px, 20vw, 92px); }
  .brand-logo { height: clamp(110px, 30.7vw, 141px); }
  .inp { font-size: 16px; } /* 16px evita el zoom automático de iOS */
}
@media (max-width: 767px) and (prefers-reduced-transparency: reduce) {
  .form-card { background: rgba(255,255,255,0.92); -webkit-backdrop-filter: none; backdrop-filter: none; }
}

/* ════════════════════════════════════════
   CAPA FIJA DE PANTALLA COMPLETA
   El acceso ocupa toda la pantalla real (incluida la zona segura y el área bajo la barra del
   navegador), así nunca se asoma el fondo verde claro de la app por abajo o por los lados.
   ════════════════════════════════════════ */
.root {
  position: fixed !important;
  inset: 0 !important;
  height: auto !important;
  min-height: 0 !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: none;
  background: #0b3d24;
}
.left-panel { height: auto !important; align-self: stretch; }
.right-panel { height: auto !important; min-height: 100% !important; }
</style>
