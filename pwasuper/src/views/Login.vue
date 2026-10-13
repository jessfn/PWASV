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
          <img src="/images/logosv.png" alt="Sembrando Vida" class="brand-logo" />
        </div>

        <!-- Encabezado -->
        <header class="form-header rise" style="--d: .06s">
          <h2 class="form-title">Bienvenido</h2>
          <p class="form-sub">Inicia sesión en la <strong>Aplicación de Seguimiento</strong></p>
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

          <div class="row-aux rise" style="--d: .22s">
            <span v-if="mayusculas" class="caps" role="status">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 4 13h4v5h8v-5h4z"/></svg>
              Bloq Mayús activado
            </span>
            <span v-else></span>
            <router-link to="/forgot-password" class="link-soft">¿Olvidaste tu contraseña?</router-link>
          </div>

          <button type="submit" class="btn-submit rise" style="--d: .26s" :disabled="loading">
            <span v-if="loading" class="spinner" aria-hidden="true"></span>
            <span class="btn-text">{{ loading ? 'Verificando…' : 'Iniciar sesión' }}</span>
            <svg v-if="!loading" class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg>
          </button>
        </form>

        <div class="sep rise" style="--d: .30s" aria-hidden="true"></div>

        <p class="signup rise" style="--d: .32s">¿No tienes cuenta? <router-link to="/register" class="link-strong">Crear cuenta</router-link></p>

        <p class="copy rise" style="--d: .36s">© 2026 Sembrando Vida · Todos los derechos reservados</p>

      </div><!-- /form-card -->
    </main>

    <SupportBubbleLogin />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
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

onMounted(() => {
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
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600&display=swap');

/* ── reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ════════════════════════════════════════
   RAÍZ — flex horizontal
   ════════════════════════════════════════ */
.root {
  display: flex;
  align-items: stretch;   /* paneles estiran al alto real del contenido */
  min-height: 100vh;
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
   TARJETA DE ACCESO — estilo Apple premium
   ════════════════════════════════════════ */
.right-panel {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.form-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 424px;
  margin: auto;
  display: flex;
  flex-direction: column;
  padding: clamp(22px, 4vh, 40px) clamp(22px, 3.2vw, 38px) clamp(18px, 3vh, 28px);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;

  background: rgba(255, 255, 255, 0.88);
  -webkit-backdrop-filter: blur(34px) saturate(1.7);
  backdrop-filter: blur(34px) saturate(1.7);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 32px;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 30px 70px -18px rgba(0, 0, 0, 0.45),
    0 10px 24px -8px rgba(0, 0, 0, 0.2);

  animation: cardIn 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes cardIn {
  from { opacity: 0; transform: translateY(24px) scale(0.965); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* entrada escalonada de cada bloque */
.rise { animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: var(--d, 0s); }
@keyframes rise {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Marca */
.brand { text-align: center; line-height: 0; overflow: hidden; height: clamp(84px, 13vh, 120px); flex-shrink: 0; }
.brand-logo { height: clamp(128px, 20vh, 184px); width: auto; max-width: 100%; object-fit: cover; object-position: top; display: block; margin: 0 auto; filter: drop-shadow(0 4px 12px rgba(21,128,61,0.2)); }

/* Encabezado */
.form-header { text-align: center; margin: clamp(10px, 2vh, 18px) 0 clamp(14px, 2.4vh, 22px); }
.form-title { font-size: clamp(26px, 3.4vh, 32px); font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; color: #0f1f16; }
.form-sub { margin-top: 8px; font-size: 14.5px; line-height: 1.45; color: #5b6b62; }
.form-sub strong { color: #166534; font-weight: 600; }

/* Avisos */
.note { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; margin-bottom: 14px; border-radius: 16px; font-size: 13.5px; line-height: 1.4; font-weight: 500; }
.note svg { width: 18px; height: 18px; flex-shrink: 0; margin-top: 1px; }
.note-ok { background: #ecfdf3; color: #166534; border: 1px solid #bbf7d0; }
.note-error { background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; }
.pop-enter-active, .pop-leave-active { transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1); }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-8px) scale(0.98); }

/* Formulario */
.form { display: flex; flex-direction: column; }
.form.shake { animation: shake 0.42s cubic-bezier(0.36, 0.07, 0.19, 0.97); }
@keyframes shake {
  10%, 90% { transform: translateX(-1px); }
  20%, 80% { transform: translateX(3px); }
  30%, 50%, 70% { transform: translateX(-6px); }
  40%, 60% { transform: translateX(6px); }
}

/* Campo con etiqueta flotante */
.field { position: relative; margin-bottom: 12px; }
.inp {
  width: 100%;
  height: 58px;
  padding: 22px 48px 6px 48px;
  font: inherit;
  font-size: 16px;
  color: #0f1f16;
  background: #f2f5f3;
  border: 1.5px solid transparent;
  border-radius: 18px;
  outline: none;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
}
.inp::placeholder { color: transparent; }
.inp:hover:not(:disabled) { background: #edf1ee; }
.inp:focus {
  background: #ffffff;
  border-color: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.16);
}
.inp:disabled { opacity: 0.6; }

.float-label {
  position: absolute;
  left: 48px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 16px;
  color: #7b8a81;
  pointer-events: none;
  transition: all 0.18s cubic-bezier(0.22, 1, 0.36, 1);
  transform-origin: left center;
}
.inp:focus + .float-label,
.inp:not(:placeholder-shown) + .float-label {
  top: 17px;
  transform: translateY(-50%) scale(0.76);
  color: #15803d;
  font-weight: 600;
}

.field-ico { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px; color: #8a9990; transition: color 0.2s; pointer-events: none; }
.field-ico svg { width: 100%; height: 100%; }
.field:focus-within .field-ico { color: #16a34a; }

.field.invalid .inp { border-color: #f43f5e; background: #fff7f8; }
.field.invalid .inp:focus { box-shadow: 0 0 0 4px rgba(244, 63, 94, 0.14); }
.field.invalid .float-label { color: #be123c; }

.eye {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  width: 44px; height: 44px; display: grid; place-items: center;
  border: 0; border-radius: 14px; background: transparent; color: #7b8a81; cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.eye svg { width: 20px; height: 20px; }
.eye:hover:not(:disabled) { background: rgba(22,163,74,0.1); color: #15803d; }
.eye:active { transform: translateY(-50%) scale(0.94); }

.hint { margin: -4px 4px 10px; font-size: 12.5px; }
.hint-error { color: #be123c; }

/* Fila auxiliar */
.row-aux { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 22px; margin: 2px 4px 16px; }
.caps { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; font-weight: 600; color: #b45309; }
.caps svg { width: 14px; height: 14px; }
.link-soft { font-size: 13.5px; font-weight: 600; color: #15803d; text-decoration: none; margin-left: auto; padding: 4px 2px; border-radius: 8px; transition: color 0.2s, opacity 0.2s; }
.link-soft:hover { color: #0f5132; text-decoration: underline; text-underline-offset: 3px; }

/* Botón principal */
.btn-submit {
  position: relative;
  display: flex; align-items: center; justify-content: center; gap: 10px;
  width: 100%; height: 56px;
  border: 0; border-radius: 18px;
  font: inherit; font-size: 16.5px; font-weight: 650; letter-spacing: -0.01em;
  color: #ffffff; cursor: pointer;
  background: linear-gradient(180deg, #22b455 0%, #15803d 100%);
  box-shadow:
    0 1px 0 rgba(255,255,255,0.35) inset,
    0 14px 26px -10px rgba(21, 128, 61, 0.65),
    0 4px 10px -4px rgba(21, 128, 61, 0.4);
  transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.25s, filter 0.2s;
  -webkit-tap-highlight-color: transparent;
}
.btn-submit:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.04); box-shadow: 0 1px 0 rgba(255,255,255,0.35) inset, 0 20px 34px -12px rgba(21,128,61,0.7), 0 6px 14px -4px rgba(21,128,61,0.45); }
.btn-submit:hover:not(:disabled) .btn-arrow { transform: translateX(3px); }
.btn-submit:active:not(:disabled) { transform: scale(0.98); }
.btn-submit:focus-visible { outline: 3px solid rgba(22,163,74,0.4); outline-offset: 3px; }
.btn-submit:disabled { cursor: progress; filter: saturate(0.85) brightness(0.98); }
.btn-arrow { width: 20px; height: 20px; transition: transform 0.2s; }
.spinner { width: 20px; height: 20px; border-radius: 50%; border: 2.5px solid rgba(255,255,255,0.4); border-top-color: #fff; animation: giro 0.75s linear infinite; }
@keyframes giro { to { transform: rotate(360deg); } }

/* Pie de la tarjeta */
.sep { height: 1px; margin: clamp(14px, 2.4vh, 22px) 8% 0; background: linear-gradient(90deg, transparent, rgba(22,101,52,0.28), transparent); }
.signup { text-align: center; margin-top: clamp(12px, 2vh, 18px); font-size: 14px; color: #5b6b62; }
.link-strong { color: #15803d; font-weight: 650; text-decoration: none; margin-left: 4px; }
.link-strong:hover { text-decoration: underline; text-underline-offset: 3px; }
.copy { text-align: center; margin-top: clamp(10px, 1.8vh, 16px); font-size: 11.5px; color: #8d9b93; }

@media (prefers-reduced-motion: reduce) {
  .form-card, .rise, .form.shake, .spinner { animation: none !important; }
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
   MÓVIL < 768px — centrado y con scroll si el teclado lo requiere
   ════════════════════════════════════════ */
@media (max-width: 767px) {
  .root { height: auto; min-height: 100dvh; overflow: visible; }
  .right-panel {
    height: auto;
    min-height: 100dvh;
    padding: max(18px, env(safe-area-inset-top)) 16px max(18px, env(safe-area-inset-bottom));
    background:
      linear-gradient(160deg, rgba(2,44,18,0.92) 0%, rgba(10,68,30,0.85) 45%, rgba(21,128,61,0.80) 100%),
      url('https://images.unsplash.com/photo-1523348837708-15d4a09cfac2?auto=format&fit=crop&w=800&q=80') center/cover no-repeat;
    background-attachment: scroll;
  }
  .form-card { border-radius: 28px; max-width: 400px; padding: 24px 22px 20px; }
  .brand { height: clamp(78px, 21vw, 104px); }
  .brand-logo { height: clamp(118px, 32vw, 156px); }
  .form-title { font-size: 27px; }
  .inp { font-size: 16px; } /* 16px evita el zoom automático en iOS */
}
</style>
