<template>
  <!-- Título de la vista unido a la barra verde superior (mismo bloque, distinguible por su franja más clara) -->
  <div class="vt-strip" role="banner">
    <div class="vt-inner">
      <div class="vt-text">
        <h1 class="vt-title">{{ title }}</h1>
        <p v-if="subtitle" class="vt-sub">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.default" class="vt-actions"><slot /></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>
