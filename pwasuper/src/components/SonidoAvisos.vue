<template>
  <section class="so">
    <span class="so__ico" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z" /><path d="M15.5 8.5a5 5 0 010 7" /><path d="M18.5 5.5a9 9 0 010 13" /></svg>
    </span>
    <div class="so__txt">
      <h3>Sonido de avisos</h3>
      <p>Un “ding” suave cuando llega una notificación con la app abierta.</p>
    </div>
    <div class="so__acc">
      <button type="button" class="so__btn" @click="escuchar">Escuchar</button>
      <button type="button" class="so__sw" role="switch" :aria-checked="activo" :class="{ on: activo }" aria-label="Sonido de avisos" @click="alternar"><i></i></button>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { sonidoActivado, activarSonido, probarSonido } from '../utils/sonidoNotificacion.js'

const activo = ref(sonidoActivado())
const alternar = () => { activo.value = !activo.value; activarSonido(activo.value); if (activo.value) probarSonido() }
const escuchar = () => { probarSonido() }
</script>

<style scoped>
.so { display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 12px 14px; align-items: center; margin: 0 0 14px; padding: 14px 16px; border-radius: 20px; background: #fff; border: 1px solid #dbe3ea; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Segoe UI', system-ui, sans-serif; }
.so__ico { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; background: #e7effb; color: #1d5fc4; }
.so__ico svg { width: 22px; height: 22px; }
.so__txt h3 { margin: 0; font-size: 0.96rem; font-weight: 650; color: #0f172a; }
.so__txt p { margin: 3px 0 0; font-size: 0.82rem; color: #475467; line-height: 1.4; }
.so__acc { display: flex; align-items: center; gap: 10px; }
.so__btn { height: 34px; padding: 0 14px; border: 1px solid #cfd9e1; border-radius: 10px; background: #fff; color: #1e293b; font-weight: 650; font-size: 0.82rem; cursor: pointer; }
.so__sw { width: 50px; height: 30px; border: 0; border-radius: 999px; background: #c3cdd6; position: relative; cursor: pointer; transition: background 0.2s; padding: 0; }
.so__sw i { position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); transition: transform 0.2s; }
.so__sw.on { background: #16a34a; }
.so__sw.on i { transform: translateX(20px); }
@media (max-width: 520px) { .so { grid-template-columns: 44px minmax(0, 1fr); } .so__acc { grid-column: 1 / -1; justify-content: space-between; } }
</style>
