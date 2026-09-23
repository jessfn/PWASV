<template>
  <div class="hm-root">
    <div class="hm-bg" aria-hidden="true"></div>

    <div class="hm-scroll">
      <div class="hm-container">

      <!-- Panel de registro: título, progreso de la jornada y selector de sección -->
      <section v-if="!modoAsistencia" class="hm-panel">
        <header class="hm-panel__head">
          <div class="hm-panel__titles">
            <span class="hm-eyebrow">Herramienta de apoyo</span>
            <h1 class="hm-title">Panel de Registro</h1>
            <p class="hm-sub">Selecciona el tipo de registro que deseas realizar</p>
          </div>
          <span class="hm-chip" :class="'hm-chip--' + estadoJornada.key">
            <i class="hm-chip__dot"></i>{{ estadoJornada.texto }}
          </span>
        </header>

        <!-- Progreso de la jornada: Inicio → Actividades → Término -->
        <ol class="hm-steps" aria-label="Progreso de la jornada">
          <li class="hm-step" :class="{ 'is-done': entradaMarcada, 'is-current': !entradaMarcada }">
            <span class="hm-step__dot">
              <svg v-if="entradaMarcada" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              <template v-else>1</template>
            </span>
            <span class="hm-step__name">Inicio</span>
            <span class="hm-step__meta">{{ horaEntradaTexto }}</span>
          </li>

          <li class="hm-step" :class="{ 'is-done': salidaMarcada, 'is-current': actividadesDisponibles, 'is-locked': !entradaMarcada }">
            <span class="hm-step__dot">
              <svg v-if="salidaMarcada" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              <svg v-else-if="!entradaMarcada" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></svg>
              <template v-else>2</template>
            </span>
            <span class="hm-step__name">Actividades</span>
            <span class="hm-step__meta">{{ !entradaMarcada ? 'Bloqueado' : (salidaMarcada ? 'Cerradas' : 'Disponible') }}</span>
          </li>

          <li class="hm-step" :class="{ 'is-done': salidaMarcada, 'is-current': actividadesDisponibles, 'is-locked': !entradaMarcada }">
            <span class="hm-step__dot">
              <svg v-if="salidaMarcada" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              <svg v-else-if="!entradaMarcada" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></svg>
              <template v-else>3</template>
            </span>
            <span class="hm-step__name">Término</span>
            <span class="hm-step__meta">{{ horaSalidaTexto }}</span>
          </li>
        </ol>

        <!-- Selector de sección (Registro | Actividades) -->
        <div class="hm-segment" role="tablist" :data-active="segmentoActivo || 'none'">
          <span class="hm-segment__thumb" aria-hidden="true"></span>

          <button
            type="button"
            role="tab"
            class="hm-segment__btn"
            :class="{ 'is-active': segmentoActivo === 'registro' }"
            :aria-selected="segmentoActivo === 'registro'"
            @click="seccionActiva = 'asistencia'"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>Registro</span>
          </button>

          <button
            type="button"
            role="tab"
            class="hm-segment__btn"
            :class="{ 'is-active': segmentoActivo === 'actividades', 'is-locked': !actividadesDisponibles }"
            :aria-selected="segmentoActivo === 'actividades'"
            @click="(!entradaMarcada || salidaMarcada) ? mostrarModalActividadesBloqueadas() : (seccionActiva = 'actividades')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            <span>Actividades</span>
            <svg v-if="!actividadesDisponibles" class="hm-segment__lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></svg>
          </button>
        </div>
      </section>

      <!-- Sistema de Asistencia Integrado -->
      <div v-if="seccionActiva === 'asistencia' || modoAsistencia" :class="modoAsistencia ? (tipoAsistencia === 'entrada' ? 'glass-card-blue relative px-0 py-2' : 'glass-card-red relative px-0 py-2') : 'relative px-0 py-2'">
        <!-- Icono de regresar (solo visible en modo asistencia) -->
        <button 
          v-if="modoAsistencia"
          @click="cancelarAsistencia"
          class="absolute top-3 left-3 w-8 h-8 sm:w-9 sm:h-9 bg-white rounded-full shadow-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50 active:scale-95 transition-all duration-200 z-20"
          title="Regresar"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        
        <div class="hm-section-head" :class="{ 'is-center': modoAsistencia }">
          <h2 class="hm-h2">Control de Jornada</h2>
          <p class="hm-hint">
            {{ modoAsistencia ? 'Completa los datos para ' + (tipoAsistencia === 'entrada' ? 'registro de inicio' : 'registro de término') : 'Registra tu inicio y término de jornada' }}
          </p>
        </div>

        <!-- Acciones de jornada (solo visibles cuando no está en modo asistencia) -->
        <div v-if="!modoAsistencia" class="hm-actions">

          <!-- Registro de Inicio -->
          <button
            type="button"
            class="hm-action hm-action--in"
            :class="{
              'is-available': !entradaMarcada && !verificandoAsistencia,
              'is-done': entradaMarcada,
              'is-loading': verificandoAsistencia
            }"
            :disabled="entradaMarcada || verificandoAsistencia"
            @click="mostrarModalEntrada"
          >
            <span v-if="verificandoAsistencia" class="hm-action__loader" aria-label="Verificando"><i class="hm-spinner"></i></span>

            <template v-if="!entradaMarcada">
              <span class="hm-action__icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
              </span>
              <span class="hm-action__title">Registro de Inicio</span>
              <span class="hm-action__sub">Inicia tu jornada</span>
              <span class="hm-action__cta">
                Registrar
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
              </span>
            </template>

            <template v-else>
              <span class="hm-action__icon hm-action__icon--done">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              </span>
              <span class="hm-action__title">Inicio Registrado</span>
              <span class="hm-action__time">{{ horaEntradaTexto }}</span>
              <span class="hm-badge hm-badge--ok">Completado</span>
            </template>
          </button>

          <!-- Registro de Término -->
          <button
            type="button"
            class="hm-action hm-action--out"
            :class="{
              'is-available': entradaMarcada && !salidaMarcada && !verificandoAsistencia,
              'is-locked': !entradaMarcada,
              'is-done': salidaMarcada,
              'is-loading': verificandoAsistencia
            }"
            :disabled="!entradaMarcada || salidaMarcada || verificandoAsistencia"
            @click="mostrarModalSalida"
          >
            <span v-if="verificandoAsistencia" class="hm-action__loader" aria-label="Verificando"><i class="hm-spinner"></i></span>

            <!-- Bloqueado: primero se registra el inicio -->
            <template v-if="!entradaMarcada">
              <span class="hm-action__icon hm-action__icon--lock">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></svg>
              </span>
              <span class="hm-action__title">Registro de Término</span>
              <span class="hm-action__sub">Primero registra tu inicio</span>
              <span class="hm-badge hm-badge--lock">Bloqueado</span>
            </template>

            <!-- Término ya registrado -->
            <template v-else-if="salidaMarcada">
              <span class="hm-action__icon hm-action__icon--done">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              </span>
              <span class="hm-action__title">Término Registrado</span>
              <span class="hm-action__time">{{ horaSalidaTexto }}</span>
              <span class="hm-badge hm-badge--ok">Completado</span>
            </template>

            <!-- Disponible -->
            <template v-else>
              <span class="hm-action__icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
              </span>
              <span class="hm-action__title">Registro de Término</span>
              <span class="hm-action__sub">Finaliza tu jornada</span>
              <span class="hm-action__cta">
                Registrar
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
              </span>
            </template>
          </button>
        </div>

        <!-- Sincronizando: pestaña pequeña unida a la barra de conexión -->
        <transition name="hm-sync">
          <div v-if="mensajeAsistencia && mensajeTipo === 'sync'" class="hm-syncbar" :style="{ top: syncTop + 'px' }" role="status" aria-live="polite">
            <i class="hm-toast__spin"></i>
            <span>{{ mensajeAsistencia }}</span>
          </div>
        </transition>

        <!-- Mensaje de estado (sincronización / éxito / error): tarjeta con aire propio -->
        <transition name="hm-toast">
          <div v-if="mensajeAsistencia && !modoAsistencia && mensajeTipo !== 'sync'" class="hm-toast" :class="'hm-toast--' + mensajeTipo" role="status" aria-live="polite">
            <span class="hm-toast__icon">
              <svg v-if="mensajeTipo === 'ok'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
              <svg v-else-if="mensajeTipo === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 18L18 6M6 6l12 12" /></svg>
              <i v-else-if="mensajeTipo === 'sync'" class="hm-toast__spin"></i>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8h.01M11 12h1v4h1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            </span>
            <span class="hm-toast__text">{{ mensajeAsistencia }}</span>
          </div>
        </transition>

        <!-- Aviso importante (un solo mensaje) -->
        <aside v-if="!modoAsistencia" class="hm-alert" role="note">
          <span class="hm-alert__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" /></svg>
          </span>
          <p class="hm-alert__title">Aviso importante</p>
          <p class="hm-alert__text">Debe registrar su inicio para acceder al módulo de actividades. El registro de término finaliza el acceso del día actual.</p>
        </aside>
        
        <!-- Formulario de Asistencia (solo visible en modo asistencia) -->
        <div v-if="modoAsistencia" class="apple-attendance-container mt-2 pt-2" :class="tipoAsistencia === 'entrada' ? 'hm-tone-in' : 'hm-tone-out'">
          <!-- Header estilo Apple -->
          <div class="apple-header-card mb-3" :class="tipoAsistencia === 'entrada' ? 'apple-header-entrada' : 'apple-header-salida'">
            <div class="flex items-center justify-center">
              <div class="apple-header-icon mr-2">
                <svg v-if="tipoAsistencia === 'entrada'" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </div>
              <h2 class="apple-header-title">
                {{ tipoAsistencia === 'entrada' ? 'Registro de Inicio' : 'Registro de Término' }}
              </h2>
            </div>
          </div>
          
          <!-- Info del usuario estilo Apple -->
          <div class="apple-user-card mb-3">
            <div class="flex items-center">
              <div class="apple-avatar" :class="tipoAsistencia === 'entrada' ? 'apple-avatar-blue' : 'apple-avatar-red'">
                <span class="apple-avatar-initials">{{ getUserInitials }}</span>
              </div>
              <div class="ml-3 flex-1">
                <p class="apple-user-name">{{ user.nombre_completo }}</p>
                <p class="apple-user-role">{{ user.cargo }}</p>
              </div>
              <div class="apple-status-badge" :class="tipoAsistencia === 'entrada' ? 'apple-badge-blue' : 'apple-badge-red'">
                {{ tipoAsistencia === 'entrada' ? 'Entrada' : 'Salida' }}
              </div>
            </div>
          </div>

          <!-- Paso 1: Ubicación -->
          <div class="apple-step-card mb-2">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center">
                <div class="apple-step-number">1</div>
                <h3 class="apple-step-title">Ubicación</h3>
              </div>
              <div v-if="latitud && longitud" class="apple-completed-badge">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Listo
              </div>
            </div>
            
          <!-- Botón de ubicación Apple circular -->
          <div class="apple-location-container">
            <div class="apple-location-wrapper">
              <!-- Botón circular principal -->
              <button
                type="button"
                @click="getUbicacion"
                :disabled="obteniendoUbicacion"
                class="apple-location-btn"
                :class="{
                  'apple-location-btn-loading': obteniendoUbicacion,
                  'apple-location-btn-success': latitud && longitud && !obteniendoUbicacion,
                  'apple-location-btn-default': !latitud && !longitud && !obteniendoUbicacion
                }"
              >
                <!-- Anillo de progreso animado -->
                <div v-if="obteniendoUbicacion" class="apple-location-ring">
                  <svg class="apple-location-ring-svg" viewBox="0 0 100 100">
                    <circle class="apple-location-ring-bg" cx="50" cy="50" r="45"/>
                    <circle class="apple-location-ring-progress" cx="50" cy="50" r="45"/>
                  </svg>
                </div>
                
                <!-- Pulso de éxito -->
                <div v-if="latitud && longitud && !obteniendoUbicacion" class="apple-location-pulse"></div>
                
                <!-- Icono central -->
                <div class="apple-location-icon">
                  <!-- Loading -->
                  <svg v-if="obteniendoUbicacion" xmlns="http://www.w3.org/2000/svg" class="h-7 w-7 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <!-- Success -->
                  <svg v-else-if="latitud && longitud" xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <!-- Default -->
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
              </button>
              
              <!-- Texto de estado -->
              <div class="apple-location-info">
                <span class="apple-location-title">
                  <span v-if="obteniendoUbicacion">Obteniendo...</span>
                  <span v-else-if="latitud && longitud">Ubicación lista</span>
                  <span v-else>Obtener GPS</span>
                </span>
                <span class="apple-location-subtitle">
                  <span v-if="obteniendoUbicacion">Espera un momento</span>
                  <span v-else-if="latitud && longitud">Coordenadas capturadas</span>
                  <span v-else>Toca para activar</span>
                </span>
              </div>
            </div>
            
            <!-- Coordenadas compactas -->
            <div v-if="latitud && longitud" class="apple-coordinates">
              <div class="apple-coord-item">
                <span class="apple-coord-label">Lat</span>
                <span class="apple-coord-value">{{ parseFloat(latitud).toFixed(6) }}</span>
              </div>
              <div class="apple-coord-divider"></div>
              <div class="apple-coord-item">
                <span class="apple-coord-label">Lon</span>
                <span class="apple-coord-value">{{ parseFloat(longitud).toFixed(6) }}</span>
              </div>
            </div>
          </div>
        </div>

          <!-- Paso 2: Imagen -->
          <div class="apple-step-card mb-2">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center">
                <div class="apple-step-number">2</div>
                <h3 class="apple-step-title">Imagen</h3>
              </div>
              <div v-if="foto" class="apple-completed-badge">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Listo
              </div>
            </div>
            
            <!-- Vista previa de la foto -->
            <div v-if="foto" class="mb-3">
              <div class="apple-image-preview">
                <img :src="foto" class="w-full h-full object-cover" />
                <div class="apple-image-overlay">
                  <button
                    @click="eliminarFoto"
                    class="apple-delete-image-btn"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span class="ml-1.5">Eliminar</span>
                  </button>
                </div>
              </div>
            </div>
            
            <!-- Botones para capturar foto -->
            <div v-if="!foto" class="apple-photo-buttons">
              <!-- Botón para tomar foto con cámara -->
              <button
                @click="tomarFotoConCamara"
                class="apple-photo-btn apple-photo-btn-camera"
              >
                <div class="apple-photo-btn-content">
                  <div class="apple-photo-btn-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <div class="apple-photo-btn-info">
                    <span class="apple-photo-btn-title">Cámara</span>
                    <span class="apple-photo-btn-subtitle">Tomar foto ahora</span>
                  </div>
                </div>
              </button>
              
              <!-- Botón para seleccionar de galería -->
              <button
                @click="seleccionarDeGaleria"
                class="apple-photo-btn apple-photo-btn-gallery"
              >
                <div class="apple-photo-btn-content">
                  <div class="apple-photo-btn-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div class="apple-photo-btn-info">
                    <span class="apple-photo-btn-title">Galería</span>
                    <span class="apple-photo-btn-subtitle">Seleccionar imagen</span>
                  </div>
                </div>
              </button>
            </div>
            
            <!-- Inputs ocultos para los diferentes tipos de captura -->
            <input
              type="file"
              accept="image/*"
              capture="environment"
              @change="onFileChange"
              class="hidden"
              ref="fileInputCamera"
            />
            <input
              type="file"
              accept="image/*"
              @change="onFileChange"
              class="hidden"
              ref="fileInputGallery"
            />
          </div>

          <!-- Paso 3: Descripción -->
          <div class="apple-step-card mb-2">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center">
                <div class="apple-step-number">3</div>
                <h3 class="apple-step-title">Descripción</h3>
              </div>
              <div v-if="descripcion.trim()" class="apple-completed-badge">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Listo
              </div>
            </div>
            
            <textarea
              v-model="descripcion"
              rows="2"
              class="apple-textarea"
              :placeholder="'Describe el lugar donde ' + (tipoAsistencia === 'entrada' ? 'inicias' : 'terminas') + ' tu jornada...'"
            ></textarea>
          </div>

          <!-- Checklist estilo Apple amarillo oscuro -->
          <div v-if="!puedeEnviarAsistencia" class="apple-checklist-card mt-2">
            <div class="apple-checklist-header">
              <div class="apple-checklist-icon">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <span class="apple-checklist-title">Completa los pasos</span>
            </div>
            <div class="apple-checklist-items">
              <!-- Ubicación -->
              <div :class="['apple-checklist-item', latitud && longitud ? 'apple-checklist-done' : 'apple-checklist-pending']">
                <div :class="['apple-checklist-check', latitud && longitud ? 'apple-check-done' : 'apple-check-pending']">
                  <svg v-if="latitud && longitud" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>Ubicación</span>
              </div>
              <!-- Imagen -->
              <div :class="['apple-checklist-item', foto ? 'apple-checklist-done' : 'apple-checklist-pending']">
                <div :class="['apple-checklist-check', foto ? 'apple-check-done' : 'apple-check-pending']">
                  <svg v-if="foto" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>Imagen</span>
              </div>
              <!-- Descripción -->
              <div :class="['apple-checklist-item', descripcion.trim() ? 'apple-checklist-done' : 'apple-checklist-pending']">
                <div :class="['apple-checklist-check', descripcion.trim() ? 'apple-check-done' : 'apple-check-pending']">
                  <svg v-if="descripcion.trim()" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span>Descripción</span>
              </div>
            </div>
          </div>
          
          <!-- Indicador de listo estilo Apple -->
          <div v-if="puedeEnviarAsistencia && !enviandoAsistencia" class="apple-ready-card mt-2">
            <div class="apple-ready-content">
              <div class="apple-ready-icon">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span class="apple-ready-text">¡Listo para registrar!</span>
            </div>
          </div>

          <!-- Botones de acción estilo Apple -->
          <div class="apple-action-buttons">
            <button
              @click="cancelarAsistencia"
              class="apple-btn-cancel"
            >
              <span>Cancelar</span>
            </button>
            
            <button
              @click="confirmarAsistencia"
              :disabled="!puedeEnviarAsistencia || enviandoAsistencia"
              class="apple-btn-submit"
              :class="[
                tipoAsistencia === 'entrada' ? 'apple-btn-entrada' : 'apple-btn-salida',
                {'apple-btn-disabled': !puedeEnviarAsistencia || enviandoAsistencia}
              ]"
            >
              <div v-if="enviandoAsistencia" class="apple-spinner">
                <div class="apple-spinner-ring"></div>
              </div>
              <template v-else>
                <svg v-if="tipoAsistencia === 'entrada'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>{{ tipoAsistencia === 'entrada' ? 'Registrar Entrada' : 'Registrar Salida' }}</span>
              </template>
            </button>
          </div>
        </div>
      </div>
      </div>

    <!-- Modal de confirmación para entrada -->
    <ConfirmModal 
      :show="showEntradaModal" 
      title="Registro de Inicio"
      :message="entradaModalMessage"
      type="confirm"
      :showConfirm="true"
      confirmText="Registrar Inicio"
      cancelText="Cancelar"
      @close="closeEntradaModal"
      @confirm="confirmarEntradaModal"
    />
    
    <!-- Modal de confirmación para salida -->
    <ConfirmModal 
      :show="showSalidaModal" 
      title="Registro de Término"
      :message="salidaModalMessage"
      type="error"
      :showConfirm="true"
      confirmText="Registrar Término"
      cancelText="Cancelar"
      @close="closeSalidaModal"
      @confirm="confirmarSalidaModal"
    />

    <!-- Modal de información para actividades bloqueadas -->
    <ConfirmModal 
      :show="showActividadesBloqueadasModal" 
      title=""
      :message="actividadesBloqueadasModalMessage"
      type="info"
      :showConfirm="false"
      cancelText="Entendido"
      @close="closeActividadesBloqueadasModal"
    />

    <!-- Formulario de registro normal (solo cuando no está en modo asistencia) -->
    <div v-if="seccionActiva === 'actividades' && !modoAsistencia" class="apple-activities-container">
      <!-- Mensaje de estado de actividades bloqueadas -->
      <div v-if="!entradaMarcada || salidaMarcada" class="apple-warning-card mb-4">
        <div class="flex items-center">
          <div class="apple-warning-icon">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="apple-warning-title">Registro de actividades bloqueado</h3>
            <p class="apple-warning-text">
              <span v-if="!entradaMarcada">Debes marcar tu entrada primero para registrar actividades.</span>
              <span v-else-if="salidaMarcada">Has marcado tu salida. No puedes registrar más actividades hoy.</span>
            </p>
          </div>
        </div>
      </div>

      <!-- Header estilo Apple morado -->
      <div class="apple-header-card apple-header-purple mb-3">
        <div class="flex items-center justify-center">
          <div class="apple-header-icon mr-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          </div>
          <h2 class="apple-header-title">
            Registro de Actividades
          </h2>
        </div>
      </div>
      
      <!-- Info del usuario estilo Apple -->
      <div class="apple-user-card mb-3">
        <div class="flex items-center">
          <div class="apple-avatar apple-avatar-purple">
            <span class="apple-avatar-initials">{{ getUserInitials }}</span>
          </div>
          <div class="ml-3 flex-1">
            <p class="apple-user-name">{{ user.nombre_completo }}</p>
            <p class="apple-user-role">{{ user.cargo }}</p>
          </div>
          <div class="apple-status-badge apple-badge-purple">
            Actividades
          </div>
        </div>
      </div>

      <form @submit.prevent="enviarRegistro" :class="{ 'opacity-50 pointer-events-none': !entradaMarcada || salidaMarcada }">
        <!-- Paso 1: Ubicación -->
        <div class="apple-step-card-purple mb-2">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
              <div class="apple-step-number-purple">1</div>
              <h3 class="apple-step-title">Ubicación</h3>
            </div>
            <div v-if="latitudRegistro && longitudRegistro" class="apple-completed-badge">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Listo
            </div>
          </div>
          
          <!-- Botón de ubicación Apple circular para actividades -->
          <div class="apple-location-container">
            <div class="apple-location-wrapper">
              <!-- Botón circular principal -->
              <button
                type="button"
                @click="getUbicacionRegistro"
                :disabled="!entradaMarcada || salidaMarcada || obteniendoUbicacionRegistro"
                class="apple-location-btn"
                :class="{
                  'apple-location-btn-loading': obteniendoUbicacionRegistro,
                  'apple-location-btn-disabled': !entradaMarcada || salidaMarcada,
                  'apple-location-btn-success': latitudRegistro && longitudRegistro && entradaMarcada && !salidaMarcada && !obteniendoUbicacionRegistro,
                  'apple-location-btn-default': entradaMarcada && !salidaMarcada && !latitudRegistro && !longitudRegistro && !obteniendoUbicacionRegistro
                }"
              >
                <!-- Pulso de éxito -->
                <div v-if="latitudRegistro && longitudRegistro && entradaMarcada && !salidaMarcada" class="apple-location-pulse"></div>
                
                <!-- Icono central -->
                <div class="apple-location-icon">
                  <!-- Bloqueado -->
                  <svg v-if="!entradaMarcada || salidaMarcada" xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <!-- Success -->
                  <svg v-else-if="latitudRegistro && longitudRegistro" xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <!-- Default -->
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
              </button>
              
              <!-- Texto de estado -->
              <div class="apple-location-info">
                <span class="apple-location-title">
                  <span v-if="!entradaMarcada">Bloqueado</span>
                  <span v-else-if="salidaMarcada">Cerrado</span>
                  <span v-else-if="obteniendoUbicacionRegistro">Obteniendo...</span>
                  <span v-else-if="latitudRegistro && longitudRegistro">Ubicación lista</span>
                  <span v-else>Obtener GPS</span>
                </span>
                <span class="apple-location-subtitle">
                  <span v-if="!entradaMarcada">Marca entrada primero</span>
                  <span v-else-if="salidaMarcada">Jornada finalizada</span>
                  <span v-else-if="latitudRegistro && longitudRegistro">Coordenadas capturadas</span>
                  <span v-else>Toca para activar</span>
                </span>
              </div>
            </div>
            
            <!-- Coordenadas compactas -->
            <div v-if="latitudRegistro && longitudRegistro && entradaMarcada && !salidaMarcada" class="apple-coordinates">
              <div class="apple-coord-item">
                <span class="apple-coord-label">Lat</span>
                <span class="apple-coord-value">{{ parseFloat(latitudRegistro).toFixed(6) }}</span>
              </div>
              <div class="apple-coord-divider"></div>
              <div class="apple-coord-item">
                <span class="apple-coord-label">Lon</span>
                <span class="apple-coord-value">{{ parseFloat(longitudRegistro).toFixed(6) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Paso 2: Modalidad - Campo o Gabinete -->
        <div class="apple-step-card-purple mb-2">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
              <div class="apple-step-number-purple">2</div>
              <h3 class="apple-step-title">Modalidad</h3>
            </div>
            <div v-if="tipoActividad" class="apple-completed-badge">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Listo
            </div>
          </div>
          
          <!-- Contenedor de opciones con estilo vidrio líquido compacto -->
          <div class="relative">
            <div class="grid grid-cols-2 gap-2">
              <!-- Opción Campo -->
              <div 
                @click="entradaMarcada && !salidaMarcada && (tipoActividad = 'campo')"
                :class="[
                  'relative overflow-hidden rounded-xl p-3 cursor-pointer transition-all duration-300 transform hover:scale-[1.02] border',
                  entradaMarcada && !salidaMarcada ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
                  tipoActividad === 'campo' ? 
                    'bg-gradient-to-br from-green-600/25 via-green-700/20 to-green-800/25 border-green-600/70 shadow-lg shadow-green-600/20' : 
                    'bg-gradient-to-br from-gray-50/80 via-white/60 to-gray-100/40 border-gray-200/60 hover:border-green-300/40 hover:from-green-50/30 hover:via-green-25/20 hover:to-green-50/15'
                ]"
                style="backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);"
              >
                <!-- Efecto de vidrio líquido sutil -->
                <div class="absolute inset-0 bg-gradient-to-br from-white/20 via-transparent to-transparent opacity-60 rounded-xl"></div>
                <div class="absolute bottom-0 right-0 w-12 h-12 bg-gradient-to-tl from-green-600/25 to-transparent rounded-full blur-lg"></div>
                
                <div class="relative z-10 text-center">
                  <div class="flex justify-center mb-1.5">
                    <div :class="[
                      'w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300',
                      tipoActividad === 'campo' ? 
                        'bg-green-700 text-white shadow-md shadow-green-700/40' : 
                        'bg-gray-100 text-gray-500 border border-gray-200'
                    ]">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                      </svg>
                    </div>
                  </div>
                  <h3 :class="[
                    'font-medium text-xs mb-0.5 transition-colors duration-300',
                    tipoActividad === 'campo' ? 'text-green-900' : 'text-gray-600'
                  ]">Campo</h3>
                  <p :class="[
                    'text-xs leading-tight transition-colors duration-300',
                    tipoActividad === 'campo' ? 'text-green-800' : 'text-gray-400'
                  ]">Trabajo en terreno</p>
                </div>
                
                <!-- Indicador de selección pequeño -->
                <div v-if="tipoActividad === 'campo'" class="absolute top-1.5 right-1.5">
                  <div class="w-4 h-4 bg-green-700 rounded-full flex items-center justify-center shadow-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              </div>

              <!-- Opción Gabinete -->
              <div 
                @click="entradaMarcada && !salidaMarcada && (tipoActividad = 'gabinete')"
                :class="[
                  'relative overflow-hidden rounded-xl p-3 cursor-pointer transition-all duration-300 transform hover:scale-[1.02] border',
                  entradaMarcada && !salidaMarcada ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
                  tipoActividad === 'gabinete' ? 
                    'bg-gradient-to-br from-orange-600/25 via-red-600/20 to-orange-700/25 border-orange-600/70 shadow-lg shadow-orange-600/20' : 
                    'bg-gradient-to-br from-gray-50/80 via-white/60 to-gray-100/40 border-gray-200/60 hover:border-orange-300/40 hover:from-orange-50/30 hover:via-red-25/20 hover:to-orange-50/15'
                ]"
                style="backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);"
              >
                <!-- Efecto de vidrio líquido sutil -->
                <div class="absolute inset-0 bg-gradient-to-br from-white/20 via-transparent to-transparent opacity-60 rounded-xl"></div>
                <div class="absolute bottom-0 right-0 w-12 h-12 bg-gradient-to-tl from-orange-600/25 to-transparent rounded-full blur-lg"></div>
                
                <div class="relative z-10 text-center">
                  <div class="flex justify-center mb-1.5">
                    <div :class="[
                      'w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300',
                      tipoActividad === 'gabinete' ? 
                        'bg-orange-700 text-white shadow-md shadow-orange-700/40' : 
                        'bg-gray-100 text-gray-500 border border-gray-200'
                    ]">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                  </div>
                  <h3 :class="[
                    'font-medium text-xs mb-0.5 transition-colors duration-300',
                    tipoActividad === 'gabinete' ? 'text-orange-900' : 'text-gray-600'
                  ]">Gabinete</h3>
                  <p :class="[
                    'text-xs leading-tight transition-colors duration-300',
                    tipoActividad === 'gabinete' ? 'text-orange-800' : 'text-gray-400'
                  ]">Trabajo de oficina</p>
                </div>
                
                <!-- Indicador de selección pequeño -->
                <div v-if="tipoActividad === 'gabinete'" class="absolute top-1.5 right-1.5">
                  <div class="w-4 h-4 bg-orange-700 rounded-full flex items-center justify-center shadow-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Mensaje de error si no está seleccionado -->
            <div v-if="!tipoActividad && (entradaMarcada && !salidaMarcada)" class="mt-1.5 text-center">
              <p class="text-xs text-red-500 font-medium animate-pulse">Por favor selecciona la modalidad</p>
            </div>
          </div>
        </div>

        <!-- Paso 3: Categoría de Actividad -->
        <div class="apple-step-card-purple mb-2">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
              <div class="apple-step-number-purple">3</div>
              <h3 class="apple-step-title">Categoría</h3>
            </div>
            <div v-if="categoriaActividad && (categoriaActividad !== 'Otro' || categoriaActividadOtro.trim())" class="apple-completed-badge">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Listo
            </div>
          </div>
          <label class="block text-xs font-medium mb-2 flex items-center"
                 :class="{ 
                   'text-gray-400': !entradaMarcada || salidaMarcada || !tipoActividad,
                   'text-gray-700': entradaMarcada && !salidaMarcada && tipoActividad
                 }">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1.5" :class="{ 'text-gray-400': !entradaMarcada || salidaMarcada || !tipoActividad, 'text-purple-600': entradaMarcada && !salidaMarcada && tipoActividad }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
            Tipo de Actividad <span class="text-red-500 text-sm ml-1">*</span>
          </label>
          
          <div class="relative">
            <select
              v-model="categoriaActividad"
              :disabled="!entradaMarcada || salidaMarcada || !tipoActividad"
              class="apple-select w-full text-sm appearance-none pr-10"
              :class="{ 
                'opacity-50 cursor-not-allowed': !entradaMarcada || salidaMarcada || !tipoActividad,
                'border-red-400': !categoriaActividad && tipoActividad && entradaMarcada && !salidaMarcada
              }"
            >
              <option value="" disabled>{{ !tipoActividad ? '-- Primero selecciona la modalidad --' : '-- Selecciona el tipo de actividad --' }}</option>
              <option v-for="categoria in categoriasActividad" :key="categoria" :value="categoria">
                {{ categoria }}
              </option>
            </select>
            <!-- Icono de flecha para el select -->
            <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-purple-500">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
          
          <!-- Mensaje de error si no se ha seleccionado tipo de actividad -->
          <div v-if="!categoriaActividad && tipoActividad && entradaMarcada && !salidaMarcada" class="mt-1.5">
            <p class="text-xs text-red-500 font-medium animate-pulse">Por favor selecciona el tipo de actividad</p>
          </div>

          <!-- Campo para especificar "Otro" si se selecciona esa opción -->
          <div v-if="categoriaActividad === 'Otro'" class="mt-3">
            <label class="apple-input-label flex items-center mb-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1.5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Especifica cuál <span class="text-red-500 text-sm ml-1">*</span>
            </label>
            
            <input
              type="text"
              v-model="categoriaActividadOtro"
              :disabled="!entradaMarcada || salidaMarcada"
              class="apple-input w-full text-sm"
              :class="{ 
                'opacity-50 cursor-not-allowed': !entradaMarcada || salidaMarcada,
                'border-red-400': categoriaActividad === 'Otro' && !categoriaActividadOtro.trim() && entradaMarcada && !salidaMarcada
              }"
              placeholder="Escribe el tipo de actividad..."
              maxlength="200"
            />
            
            <!-- Mensaje de error si no se ha especificado el otro tipo -->
            <div v-if="categoriaActividad === 'Otro' && !categoriaActividadOtro.trim() && entradaMarcada && !salidaMarcada" class="mt-1.5">
              <p class="text-xs text-red-500 font-medium animate-pulse">Por favor especifica el tipo de actividad</p>
            </div>
          </div>
        </div>

        <!-- Paso 4: Imagen -->
        <div class="apple-step-card-purple mb-2">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
              <div class="apple-step-number-purple">4</div>
              <h3 class="apple-step-title">Evidencia Fotográfica</h3>
            </div>
            <div v-if="fotoRegistro" class="apple-completed-badge">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Listo
            </div>
          </div>
          
          <!-- Vista previa de la foto -->
          <div v-if="fotoRegistro" class="apple-photo-preview mb-3">
            <div class="apple-photo-container">
              <img :src="fotoRegistro" class="w-full h-full object-cover" />
              <div class="apple-photo-overlay">
                <button
                  @click="eliminarFotoRegistro"
                  :disabled="!entradaMarcada || salidaMarcada"
                  class="apple-photo-delete-btn"
                  :class="{ 'opacity-50 cursor-not-allowed': !entradaMarcada || salidaMarcada }"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  <span>Eliminar</span>
                </button>
              </div>
            </div>
          </div>
          
          <!-- Botones para capturar foto estilo Apple -->
          <div v-if="!fotoRegistro" class="apple-photo-buttons">
            <!-- Botón para tomar foto con cámara -->
            <button
              @click="tomarFotoConCamaraRegistro"
              :disabled="!entradaMarcada || salidaMarcada"
              class="apple-photo-btn apple-photo-btn-camera-dark"
              :class="{ 'opacity-50 cursor-not-allowed': !entradaMarcada || salidaMarcada }"
            >
              <div class="apple-photo-btn-icon">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <span class="apple-photo-btn-text">
                <span v-if="entradaMarcada && !salidaMarcada">Cámara</span>
                <span v-else-if="!entradaMarcada">Bloqueado</span>
                <span v-else>Bloqueado</span>
              </span>
            </button>
            
            <!-- Botón para seleccionar de galería -->
            <button
              @click="seleccionarDeGaleriaRegistro"
              :disabled="!entradaMarcada || salidaMarcada"
              class="apple-photo-btn apple-photo-btn-gallery-dark"
              :class="{ 'opacity-50 cursor-not-allowed': !entradaMarcada || salidaMarcada }"
            >
              <div class="apple-photo-btn-icon">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <span class="apple-photo-btn-text">
                <span v-if="entradaMarcada && !salidaMarcada">Galería</span>
                <span v-else-if="!entradaMarcada">Bloqueado</span>
                <span v-else>Bloqueado</span>
              </span>
            </button>
          </div>
          
          <!-- Inputs ocultos para los diferentes tipos de captura -->
          <input
            type="file"
            accept="image/*"
            capture="environment"
            @change="onFileChangeRegistro"
            :disabled="!entradaMarcada || salidaMarcada"
            class="hidden"
            ref="fileInputCameraRegistro"
          />
          <input
            type="file"
            accept="image/*"
            @change="onFileChangeRegistro"
            :disabled="!entradaMarcada || salidaMarcada"
            class="hidden"
            ref="fileInputGalleryRegistro"
          />
        </div>

        <!-- Paso 5: Descripción (Obligatorio) -->
        <div class="apple-step-card-purple mb-2">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center">
              <div class="apple-step-number-purple">5</div>
              <h3 class="apple-step-title">Descripción</h3>
            </div>
            <div v-if="descripcionRegistro.trim()" class="apple-completed-badge">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span>Completado</span>
            </div>
            <span v-else class="text-xs text-red-400 font-medium">* Requerido</span>
          </div>
          
          <textarea
            v-model="descripcionRegistro"
            id="descripcionRegistro"
            rows="3"
            :disabled="!entradaMarcada || salidaMarcada"
            class="apple-textarea w-full"
            :class="{ 'opacity-50': !entradaMarcada || salidaMarcada }"
            :placeholder="entradaMarcada && !salidaMarcada ? 'Describe la actividad o añade notas...' : !entradaMarcada ? 'Marca entrada primero...' : 'Función bloqueada...'"
          ></textarea>
        </div>

        <!-- Checklist de progreso estilo Apple amarillo oscuro -->
        <div v-if="entradaMarcada && !salidaMarcada && (!latitudRegistro || !longitudRegistro || !fotoRegistro || !tipoActividad || !categoriaActividad || (categoriaActividad === 'Otro' && !categoriaActividadOtro.trim()) || !descripcionRegistro.trim())" 
             class="apple-checklist-card mb-4">
          <div class="apple-checklist-header">
            <div class="apple-checklist-icon">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <span class="apple-checklist-title">Completa estos pasos</span>
          </div>
          <div class="apple-checklist-items">
            <!-- Ubicación -->
            <div :class="['apple-checklist-item', latitudRegistro && longitudRegistro ? 'apple-checklist-item-done' : 'apple-checklist-item-pending']">
              <div :class="['apple-checklist-circle', latitudRegistro && longitudRegistro ? 'apple-checklist-circle-done' : 'apple-checklist-circle-pending']">
                <svg v-if="latitudRegistro && longitudRegistro" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span>Ubicación</span>
            </div>
            <!-- Imagen -->
            <div :class="['apple-checklist-item', fotoRegistro ? 'apple-checklist-item-done' : 'apple-checklist-item-pending']">
              <div :class="['apple-checklist-circle', fotoRegistro ? 'apple-checklist-circle-done' : 'apple-checklist-circle-pending']">
                <svg v-if="fotoRegistro" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span>Imagen</span>
            </div>
            <!-- Modalidad -->
            <div :class="['apple-checklist-item', tipoActividad ? 'apple-checklist-item-done' : 'apple-checklist-item-pending']">
              <div :class="['apple-checklist-circle', tipoActividad ? 'apple-checklist-circle-done' : 'apple-checklist-circle-pending']">
                <svg v-if="tipoActividad" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span>Modalidad</span>
            </div>
            <!-- Categoría -->
            <div :class="['apple-checklist-item', categoriaActividad && (categoriaActividad !== 'Otro' || categoriaActividadOtro.trim()) ? 'apple-checklist-item-done' : 'apple-checklist-item-pending']">
              <div :class="['apple-checklist-circle', categoriaActividad && (categoriaActividad !== 'Otro' || categoriaActividadOtro.trim()) ? 'apple-checklist-circle-done' : 'apple-checklist-circle-pending']">
                <svg v-if="categoriaActividad && (categoriaActividad !== 'Otro' || categoriaActividadOtro.trim())" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span>Categoría</span>
            </div>
            <!-- Descripción -->
            <div :class="['apple-checklist-item', descripcionRegistro.trim() ? 'apple-checklist-item-done' : 'apple-checklist-item-pending']">
              <div :class="['apple-checklist-circle', descripcionRegistro.trim() ? 'apple-checklist-circle-done' : 'apple-checklist-circle-pending']">
                <svg v-if="descripcionRegistro.trim()" xmlns="http://www.w3.org/2000/svg" class="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span>Descripción</span>
            </div>
          </div>
        </div>

        <!-- Indicador de listo para enviar estilo Apple -->
        <div v-if="entradaMarcada && !salidaMarcada && latitudRegistro && longitudRegistro && fotoRegistro && tipoActividad && categoriaActividad && (categoriaActividad !== 'Otro' || categoriaActividadOtro.trim()) && descripcionRegistro.trim()" 
             class="apple-ready-card mb-4">
          <div class="flex items-center justify-center">
            <div class="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center mr-2 animate-bounce">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <span class="text-sm font-semibold text-green-700">Todo listo para enviar</span>
          </div>
        </div>

        <!-- Botón enviar -->
        <button
          type="submit"
          :disabled="!latitudRegistro || !longitudRegistro || !fotoRegistro || !tipoActividad || !categoriaActividad || (categoriaActividad === 'Otro' && !categoriaActividadOtro.trim()) || !descripcionRegistro.trim() || enviando || !entradaMarcada || salidaMarcada"
          :class="['glass-button-registro w-full', (!latitudRegistro || !longitudRegistro || !fotoRegistro || !tipoActividad || !categoriaActividad || (categoriaActividad === 'Otro' && !categoriaActividadOtro.trim()) || !descripcionRegistro.trim() || enviando || !entradaMarcada || salidaMarcada) ? 'opacity-50 cursor-not-allowed' : '']"
        >
          <span v-if="enviando" class="flex items-center justify-center">
            <svg
              class="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Enviando...
          </span>
          <span v-else-if="!entradaMarcada">Marca entrada primero</span>
          <span v-else-if="salidaMarcada">Actividades finalizadas</span>
          <span v-else>Guardar registro</span>
        </button>
      </form>
    </div>

    <!-- Mensajes de error/información -->
    <transition name="fade">
      <div
        v-if="error"
        :class="isInfoMessage ? 
          'mb-2 bg-green-50 border-l-3 border-green-500 text-green-700 p-2 rounded shadow-sm' : 
          'mb-2 bg-red-100 border-l-3 border-red-500 text-red-700 p-2 rounded'"
        role="alert"
      >
        <p class="font-semibold text-xs flex items-center">
          <svg v-if="isInfoMessage" xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          {{ isInfoMessage ? 'Info' : 'Error' }}
        </p>
        <p class="text-xs mt-0.5">{{ error }}</p>
      </div>
    </transition>

    </div>

    <!-- Modal de confirmación -->
    <Modal 
      :show="showModal" 
      title="¡Éxito!"
      :message="modalMessage"
      @close="closeSuccessModal"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import { API_URL, checkInternetConnection, getOfflineMessage } from '../utils/network.js';
import Modal from '../components/Modal.vue';
import ConfirmModal from '../components/ConfirmModal.vue';
import asistenciasService from '../services/asistenciasService.js';
import offlineService from '../services/offlineService.js';
import syncService from '../services/syncService.js';
import geoLocationService from '../services/geoLocationService.js';
import { obtenerUbicacionSimple } from '../services/geoLocationSimple.js';
import { compressImage, blobToFile } from '../utils/imageCompressor.js';

// Referencias y estado para asistencia
const modoAsistencia = ref(false);
const tipoAsistencia = ref(''); // 'entrada' o 'salida'
const entradaMarcada = ref(false);
const salidaMarcada = ref(false);
const enviandoAsistencia = ref(false);
const obteniendoUbicacion = ref(false);
const obteniendoUbicacionRegistro = ref(false);
const syncTop = ref(112);
function medirSyncTop() {
  const el = document.querySelector('.cs-strip');
  if (el) syncTop.value = Math.round(el.getBoundingClientRect().bottom) - 1;
}
onMounted(() => { medirSyncTop(); window.addEventListener('resize', medirSyncTop); });
onUnmounted(() => window.removeEventListener('resize', medirSyncTop));
const mensajeAsistencia = ref('');
watch(() => mensajeAsistencia.value, () => nextTick(medirSyncTop));
const datosEntrada = ref({});
const datosSalida = ref({});
const asistenciaHoy = ref(null);
const verificandoAsistencia = ref(false);

// Referencias y estado para asistencia (datos del formulario)
const latitud = ref(null);
const longitud = ref(null);
const foto = ref(null);
const archivoFoto = ref(null);
const descripcion = ref("");

// Referencias y estado para registro normal
const latitudRegistro = ref(null);
const longitudRegistro = ref(null);
const fotoRegistro = ref(null);
const archivoFotoRegistro = ref(null);
const descripcionRegistro = ref("");
const tipoActividad = ref(""); // Nuevo: campo para tipo de actividad

// Nuevos campos para categoría de actividad
const categoriaActividad = ref(""); // Selector de categoría obligatorio
const categoriaActividadOtro = ref(""); // Campo de texto si se selecciona "Otro"

// Lista de opciones de categoría de actividad
const categoriasActividad = [
  "Acompañamiento técnico",
  "Productivas directas",
  "Ahorro y trámites financieros",
  "Capacitación / talleres / cursos",
  "Difusión y comunicación",
  "Eventos comunitarios / ferias / tianguis",
  "Reuniones y asambleas",
  "Trabajo administrativo y captura",
  "Viveros y biofábricas",
  "Otro"
];

// Referencias generales
const fileInput = ref(null);
const fileInputRegistro = ref(null);
// Nuevas referencias para los diferentes tipos de captura
const fileInputCamera = ref(null);
const fileInputGallery = ref(null);
const fileInputCameraRegistro = ref(null);
const fileInputGalleryRegistro = ref(null);
const historial = ref([]);
const enviando = ref(false);
const error = ref(null);
const router = useRouter();
const isOnline = ref(true);
const showModal = ref(false);
const modalMessage = ref('');

// Variables para modales de confirmación
const showEntradaModal = ref(false);
const showSalidaModal = ref(false);
const showActividadesBloqueadasModal = ref(false);
const entradaModalMessage = ref('');
const salidaModalMessage = ref('');
const actividadesBloqueadasModalMessage = ref('');

// Control de secciones activas
const seccionActiva = ref('asistencia'); // 'asistencia' o 'actividades'

// ---- Estado visual de la jornada (solo presentación; no altera la lógica) ----
// Actividades solo está disponible con entrada marcada y sin salida.
const actividadesDisponibles = computed(() => entradaMarcada.value && !salidaMarcada.value);

const estadoJornada = computed(() => {
  if (salidaMarcada.value) return { key: 'done', texto: 'Jornada finalizada' };
  if (entradaMarcada.value) return { key: 'active', texto: 'En jornada' };
  return { key: 'idle', texto: 'Sin iniciar' };
});

// Hora mostrada en cada paso de la línea de tiempo
const horaEntradaTexto = computed(() => {
  if (!entradaMarcada.value) return 'Pendiente';
  if (asistenciaHoy.value && asistenciaHoy.value.entrada) return formatearHora(asistenciaHoy.value.entrada);
  return datosEntrada.value?.hora || 'Registrada';
});

const horaSalidaTexto = computed(() => {
  if (!salidaMarcada.value) return entradaMarcada.value ? 'En curso' : 'Bloqueado';
  if (asistenciaHoy.value && asistenciaHoy.value.salida) return formatearHora(asistenciaHoy.value.salida);
  return datosSalida.value?.hora || 'Registrada';
});

// Tipo visual del mensaje de estado (éxito / error / sincronizando / aviso / info)
const mensajeTipo = computed(() => {
  const m = mensajeAsistencia.value || '';
  if (/error/i.test(m)) return 'error';
  if (/[ée]xito|exitosa|registrada|completada/i.test(m)) return 'ok';
  if (/sincroniz|progreso/i.test(m)) return 'sync';
  if (/^ya|offline|sin conexi/i.test(m)) return 'warn';
  return 'info';
});

// Posición del "pulgar" del control segmentado (null = ninguno activo)
const segmentoActivo = computed(() => {
  if (seccionActiva.value === 'asistencia') return 'registro';
  if (seccionActiva.value === 'actividades' && actividadesDisponibles.value) return 'actividades';
  return null;
});

// Función para obtener timestamp CDMX exacto (igual que en la barra verde)
function obtenerTimestampCDMX() {
  const now = new Date();
  
  // Configurar para zona horaria de CDMX (America/Mexico_City)
  const formatter = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Mexico_City',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3
  });
  
  // Obtener la fecha/hora formateada para CDMX
  const fechaHoraCDMX = formatter.format(now);
  
  // Convertir a formato ISO con zona horaria de México
  // El formato 'sv-SE' nos da: YYYY-MM-DD HH:mm:ss.sss
  // Lo convertimos a: YYYY-MM-DDTHH:mm:ss.sss-06:00
  const isoString = fechaHoraCDMX.replace(' ', 'T') + '-06:00';
  
  console.log(`🕐 Timestamp CDMX generado: ${isoString}`);
  return isoString;
}

// Obtener información del usuario del localStorage
const user = computed(() => {
  const storedUser = localStorage.getItem("user");
  if (!storedUser) {
    router.push("/login");
    return {};
  }
  return JSON.parse(storedUser);
});

// Determinar si el mensaje es de tipo información (sin conexión) o error
const isInfoMessage = computed(() => {
  if (!error.value) return false;
  
  // Palabras clave para mensajes informativos/positivos
  const infoKeywords = [
    'Sin conexión',
    '¡Excelente!',
    'Buena precisión',
    'Precisión aceptable',
    'Ubicación obtenida',
    'Se usó ubicación',
    'Funciona sin internet',
    'modo offline',
    'caché offline',
    'precisión de',
    'Registro con precisión'
  ];
  
  // Verificar si el mensaje contiene alguna palabra clave informativa
  const isInfo = infoKeywords.some(keyword => 
    error.value.toLowerCase().includes(keyword.toLowerCase())
  );
  
  return isInfo;
});

// Función para obtener las iniciales del usuario
const getUserInitials = computed(() => {
  if (user.value && user.value.nombre_completo) {
    const names = user.value.nombre_completo.split(' ');
    return names.length >= 2 ? 
      (names[0][0] + names[1][0]).toUpperCase() : 
      names[0].substring(0, 2).toUpperCase();
  }
  return 'US';
});

// Computed para verificar si se pueden enviar los datos de asistencia
const puedeEnviarAsistencia = computed(() => {
  return latitud.value && longitud.value && foto.value && descripcion.value.trim();
});

// Funciones para el sistema de asistencia
function iniciarAsistencia(tipo) {
  modoAsistencia.value = true;
  tipoAsistencia.value = tipo;
  limpiarDatosAsistencia();
  error.value = null;
  mensajeAsistencia.value = '';
  
  // Obtener ubicación automáticamente al iniciar el proceso de asistencia
  console.log(`🚀 Iniciando proceso de ${tipo}, obteniendo ubicación automáticamente...`);
  getUbicacion();
}

function limpiarDatosAsistencia() {
  latitud.value = null;
  longitud.value = null;
  foto.value = null;
  archivoFoto.value = null;
  descripcion.value = "";
  
  // Limpiar todos los inputs de archivo
  if (fileInput.value) {
    fileInput.value.value = "";
  }
  if (fileInputCamera.value) {
    fileInputCamera.value.value = "";
  }
  if (fileInputGallery.value) {
    fileInputGallery.value.value = "";
  }
}

function cancelarAsistencia() {
  modoAsistencia.value = false;
  tipoAsistencia.value = '';
  limpiarDatosAsistencia();
}

async function confirmarAsistencia() {
  if (!puedeEnviarAsistencia.value || enviandoAsistencia.value) return;
  
  enviandoAsistencia.value = true;
  error.value = null;
  
  try {
    // Verificar conexión a internet antes de enviar
    isOnline.value = await checkInternetConnection();
    
    if (!isOnline.value) {
      // **MODO OFFLINE: Guardar datos localmente**
      console.log('📴 Sin conexión - Guardando asistencia offline');
      
      // Guardar en almacenamiento offline usando IndexedDB
      await offlineService.guardarAsistenciaOffline(
        user.value.id,
        tipoAsistencia.value,
        latitud.value,
        longitud.value,
        descripcion.value,
        archivoFoto.value
      );
      
      // Simular datos de respuesta para el estado local
      const horaActual = new Date().toLocaleTimeString('es-MX', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Mexico_City'
      });
      
      // Actualizar estado local
      if (tipoAsistencia.value === 'entrada') {
        entradaMarcada.value = true;
        datosEntrada.value = {
          hora: horaActual,
          descripcion: descripcion.value,
          latitud: latitud.value,
          longitud: longitud.value,
          foto_url: foto.value // URL local temporal
        };
      } else {
        salidaMarcada.value = true;
        datosSalida.value = {
          hora: horaActual,
          descripcion: descripcion.value,
          latitud: latitud.value,
          longitud: longitud.value,
          foto_url: foto.value // URL local temporal
        };
      }
      
      // Mostrar mensaje informativo offline
      mensajeAsistencia.value = `${tipoAsistencia.value === 'entrada' ? 'Registro de inicio' : 'Registro de término'} guardado offline. Se enviará automáticamente cuando tengas conexión.`;
      modalMessage.value = `¡${tipoAsistencia.value === 'entrada' ? 'Inicio' : 'Término'} registrado! Se sincronizará cuando recuperes la conexión.`;
      showModal.value = true;
      
      // Salir del modo asistencia
      modoAsistencia.value = false;
      tipoAsistencia.value = '';
      limpiarDatosAsistencia();
      
      // Guardar estado en localStorage
      guardarEstadoAsistencia();
      
      // Limpiar mensaje después de 8 segundos (más tiempo para modo offline)
      setTimeout(() => {
        mensajeAsistencia.value = '';
      }, 8000);
      
      return;
    }

    // **MODO ONLINE: Enviar directamente al servidor**
    console.log('🌐 Conexión disponible - Enviando asistencia al servidor');
    
    // Crear FormData para enviar al servidor
    const formData = new FormData();
    formData.append("usuario_id", user.value.id.toString());
    formData.append("latitud", latitud.value);
    formData.append("longitud", longitud.value);
    formData.append("descripcion", descripcion.value);
    formData.append("foto", archivoFoto.value);
    
    // ✅ SOLUCIÓN: Agregar SIEMPRE timestamp CDMX exacto (igual que el reloj de la barra verde)
    // El servidor SIEMPRE lo debe recibir y usarlo para garantizar fecha/hora correcta
    formData.append("timestamp_offline", obtenerTimestampCDMX());

    // Determinar endpoint según tipo de asistencia y usar el servicio
    let response;
    if (tipoAsistencia.value === 'entrada') {
      response = await asistenciasService.registrarEntrada(formData);
    } else {
      response = await asistenciasService.registrarSalida(formData);
    }

    // Procesar respuesta exitosa
    if (tipoAsistencia.value === 'entrada') {
      entradaMarcada.value = true;
      datosEntrada.value = {
        hora: new Date(response.hora_entrada).toLocaleTimeString('es-MX', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'America/Mexico_City'
        }),
        descripcion: response.descripcion,
        latitud: response.latitud,
        longitud: response.longitud,
        foto_url: response.foto_url
      };
    } else {
      salidaMarcada.value = true;
      datosSalida.value = {
        hora: new Date(response.hora_salida).toLocaleTimeString('es-MX', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'America/Mexico_City'
        }),
        descripcion: response.descripcion,
        latitud: response.latitud,
        longitud: response.longitud,
        foto_url: response.foto_url
      };
    }

    // Mostrar mensaje de éxito
    mensajeAsistencia.value = response.mensaje;
    modalMessage.value = `¡${tipoAsistencia.value === 'entrada' ? 'Inicio' : 'Término'} registrado exitosamente!`;
    showModal.value = true;
    
    // Salir del modo asistencia
    modoAsistencia.value = false;
    tipoAsistencia.value = '';
    limpiarDatosAsistencia();
    
    // Guardar estado en localStorage
    guardarEstadoAsistencia();
    
    // Verificar asistencia con el backend para actualizar datos
    await verificarAsistenciaHoy();
    
    // Limpiar mensaje después de 5 segundos
    setTimeout(() => {
      mensajeAsistencia.value = '';
    }, 5000);

  } catch (err) {
    console.error('Error al enviar asistencia:', err);

    // Error HTTP explícito del servidor (4xx, 5xx con cuerpo)
    if (err.response) {
      const detalle = err.response.data?.detail || err.response.statusText || 'Error del servidor';
      error.value = "Error del servidor: " + detalle;

      if (detalle.includes('Ya existe') || detalle.includes('ya tiene registro')) {
        if (tipoAsistencia.value === 'entrada') {
          entradaMarcada.value = true;
        } else {
          salidaMarcada.value = true;
        }
        await verificarAsistenciaHoy();
      }
      return;
    }

    // Cualquier otro error (red, service worker, timeout, SSL, desconocido) → guardar offline
    console.log('📴 Error de conexión detectado, guardando asistencia offline como fallback...');
    try {
      await offlineService.guardarAsistenciaOffline(
        user.value.id,
        tipoAsistencia.value,
        latitud.value,
        longitud.value,
        descripcion.value,
        archivoFoto.value
      );

      const horaActual = new Date().toLocaleTimeString('es-MX', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Mexico_City'
      });

      if (tipoAsistencia.value === 'entrada') {
        entradaMarcada.value = true;
        datosEntrada.value = {
          hora: horaActual,
          descripcion: descripcion.value,
          latitud: latitud.value,
          longitud: longitud.value,
          foto_url: foto.value
        };
      } else {
        salidaMarcada.value = true;
        datosSalida.value = {
          hora: horaActual,
          descripcion: descripcion.value,
          latitud: latitud.value,
          longitud: longitud.value,
          foto_url: foto.value
        };
      }

      mensajeAsistencia.value = `Registro guardado localmente. Se sincronizará automáticamente cuando el servidor esté disponible.`;
      modalMessage.value = `¡Registro guardado! Se sincronizará automáticamente.`;
      showModal.value = true;
      modoAsistencia.value = false;
      tipoAsistencia.value = '';
      limpiarDatosAsistencia();
      guardarEstadoAsistencia();
      setTimeout(() => { mensajeAsistencia.value = ''; }, 8000);
    } catch (offlineErr) {
      console.error('Error guardando offline como fallback:', offlineErr);
      error.value = "Sin conexión y no se pudo guardar localmente. Intenta de nuevo.";
    }
  } finally {
    enviandoAsistencia.value = false;
  }
}

async function getUbicacion() {
  obteniendoUbicacion.value = true;
  error.value = null;

  try {
    console.log('🔍 Iniciando obtención de ubicación con MÁXIMA precisión (funciona offline)...');
    
    // Estrategia optimizada para móviles - usar watchPosition es más preciso
    const configuraciones = [
      {
        timeout: 30000, // 30 segundos - máxima precisión GPS
        enableHighAccuracy: true,
        maximumAge: 0, // CRÍTICO: NO usar caché del navegador
        minAccuracy: 20, // Buscar precisión de 20m o mejor
        maxWaitTime: 10000, // Esperar 10s por mejor precisión
        useCache: false
      },
      {
        timeout: 25000, // 25 segundos - alta precisión
        enableHighAccuracy: true,
        maximumAge: 0,
        minAccuracy: 50, // Precisión de 50m o mejor
        maxWaitTime: 8000,
        useCache: false
      },
      {
        timeout: 20000, // 20 segundos - buena precisión
        enableHighAccuracy: true,
        maximumAge: 0,
        minAccuracy: 100, // Precisión de 100m o mejor
        maxWaitTime: 6000,
        useCache: true // Último intento puede usar caché
      }
    ];
    
    // Intentar con cada configuración
    for (let i = 0; i < configuraciones.length; i++) {
      try {
        console.log(`🎯 Intento ${i + 1}/${configuraciones.length} - Buscando GPS de alta precisión...`);
        
        const location = await geoLocationService.getCurrentLocation(configuraciones[i]);

        console.log(`✅ Ubicación GPS obtenida en intento ${i + 1}:`, location);

        latitud.value = location.latitude;
        longitud.value = location.longitude;
        
        // Verificar que tenemos coordenadas válidas
        if (!latitud.value || !longitud.value) {
          throw new Error('Coordenadas inválidas recibidas');
        }
        
        // Log de precisión solo en consola (sin mostrar al usuario)
        if (location.accuracy) {
          const precision = Math.round(location.accuracy);
          if (location.accuracy <= 10) {
            console.log('🎯 EXCELENTE precisión GPS:', precision + 'm');
          } else if (location.accuracy <= 30) {
            console.log('✅ MUY BUENA precisión GPS:', precision + 'm');
          } else if (location.accuracy <= 50) {
            console.log('✅ BUENA precisión GPS:', precision + 'm');
          } else if (location.accuracy <= 100) {
            console.log('📍 Precisión GPS aceptable:', precision + 'm');
          } else {
            console.log('⚠️ Precisión GPS baja:', precision + 'm');
          }
          
          if (location.fromCache) {
            console.log('📦 Ubicación desde caché');
          }
        } else {
          console.log('✅ Ubicación GPS obtenida (precisión no disponible)');
        }
        
        return; // Salir exitosamente
        
      } catch (intentoError) {
        console.warn(`⚠️ Intento ${i + 1} falló:`, intentoError.message);
        if (i === configuraciones.length - 1) {
          // Si todos los intentos fallaron, usar fallback
          throw intentoError;
        }
        // Esperar un poco antes del siguiente intento
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
  } catch (err) {
    console.warn('⚠️ Todos los intentos de GPS fallaron, usando fallback offline:', err);
    
    // Fallback offline: usar servicio simple (funciona sin internet)
    try {
      console.log('🔄 Usando servicio simple para funcionalidad offline...');
      const simpleLocation = await obtenerUbicacionSimple();
      
      latitud.value = simpleLocation.latitude;
      longitud.value = simpleLocation.longitude;
      
      console.log('✅ Ubicación establecida con servicio offline:', simpleLocation);
      
      // Mostrar mensaje según el origen
      if (simpleLocation.source === 'default') {
        error.value = 'Se usó ubicación aproximada (modo offline). Para mayor precisión, permite el acceso a ubicación y asegúrate de estar en un área abierta.';
        setTimeout(() => error.value = null, 8000);
      } else if (simpleLocation.source === 'cache') {
        error.value = 'Se usó ubicación del caché offline. Funciona sin internet.';
        setTimeout(() => error.value = null, 5000);
      } else if (simpleLocation.accuracy && simpleLocation.accuracy > 100) {
        error.value = `Ubicación offline obtenida con precisión de ${Math.round(simpleLocation.accuracy)}m.`;
        setTimeout(() => error.value = null, 5000);
      } else {
        error.value = 'Ubicación obtenida en modo offline.';
        setTimeout(() => error.value = null, 4000);
      }
      
    } catch (offlineError) {
      console.error('❌ Error en servicio offline:', offlineError);
      
      // Último recurso: usar ubicación por defecto (siempre funciona offline)
      console.log('🆘 Aplicando ubicación de emergencia offline...');
      latitud.value = 19.4326; // Ciudad de México
      longitud.value = -99.1332;
      
      error.value = 'Se usó ubicación por defecto (modo offline). Verifica los permisos de ubicación para mayor precisión.';
      setTimeout(() => error.value = null, 10000);
    }
    
  } finally {
    obteniendoUbicacion.value = false;
  }
}

async function getUbicacionRegistro() {
  // Verificar si está habilitado para registrar actividades
  if (!entradaMarcada.value || salidaMarcada.value) {
    if (!entradaMarcada.value) {
      error.value = "Debes marcar tu entrada primero para obtener ubicación y registrar actividades.";
    } else {
      error.value = "Has marcado tu salida. No puedes registrar más actividades hoy.";
    }
    setTimeout(() => error.value = null, 4000);
    return;
  }

  error.value = null;
  obteniendoUbicacionRegistro.value = true;

  try {
    console.log('🔍 Iniciando obtención de ubicación GPS para registro (funciona offline)...');
    
    // Usar la misma estrategia optimizada para registros
    const configuraciones = [
      {
        timeout: 30000, // 30 segundos - máxima precisión para registros
        enableHighAccuracy: true,
        maximumAge: 0, // CRÍTICO: ubicación fresca para registros
        minAccuracy: 20, // Buscar 20m o mejor
        maxWaitTime: 10000,
        useCache: false
      },
      {
        timeout: 25000, // 25 segundos - alta precisión
        enableHighAccuracy: true,
        maximumAge: 0,
        minAccuracy: 50,
        maxWaitTime: 8000,
        useCache: false
      },
      {
        timeout: 20000, // 20 segundos fallback
        enableHighAccuracy: true,
        maximumAge: 0,
        minAccuracy: 100,
        maxWaitTime: 6000,
        useCache: true
      }
    ];
    
    // Intentar con cada configuración
    for (let i = 0; i < configuraciones.length; i++) {
      try {
        console.log(`🎯 Intento ${i + 1}/${configuraciones.length} para registro - Buscando GPS de alta precisión...`);
        
        const location = await geoLocationService.getCurrentLocation(configuraciones[i]);

        console.log(`✅ Ubicación GPS para registro obtenida en intento ${i + 1}:`, location);

        latitudRegistro.value = location.latitude;
        longitudRegistro.value = location.longitude;
        
        // Verificar que tenemos coordenadas válidas
        if (!latitudRegistro.value || !longitudRegistro.value) {
          throw new Error('Coordenadas inválidas para registro');
        }
        
        // Log de precisión solo en consola para registros
        if (location.accuracy) {
          const precision = Math.round(location.accuracy);
          if (location.accuracy <= 30) {
            console.log('✅ EXCELENTE precisión GPS para registro:', precision + 'm');
          } else if (location.accuracy <= 50) {
            console.log('✅ BUENA precisión GPS para registro:', precision + 'm');
          } else if (location.accuracy <= 100) {
            console.log('📍 Precisión GPS aceptable para registro:', precision + 'm');
          } else {
            console.log('⚠️ Precisión GPS baja para registro:', precision + 'm');
          }
          
          if (location.fromCache) {
            console.log('📦 Registro desde caché');
          }
        }
        
        return; // Salir exitosamente
        
      } catch (intentoError) {
        console.warn(`⚠️ Intento ${i + 1} falló para registro:`, intentoError.message);
        if (i === configuraciones.length - 1) {
          throw intentoError;
        }
        // Esperar antes del siguiente intento
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
  } catch (err) {
    console.warn('⚠️ GPS falló para registro, usando fallback offline:', err);
    
    // Fallback offline para registros
    try {
      console.log('🔄 Usando servicio offline para registro...');
      const simpleLocation = await obtenerUbicacionSimple();
      
      latitudRegistro.value = simpleLocation.latitude;
      longitudRegistro.value = simpleLocation.longitude;
      
      console.log('✅ Ubicación para registro establecida con servicio offline:', simpleLocation);
      
      // Mostrar mensaje según el origen
      if (simpleLocation.source === 'default') {
        error.value = 'Registro con ubicación aproximada (modo offline).';
        setTimeout(() => error.value = null, 6000);
      } else if (simpleLocation.source === 'cache') {
        error.value = 'Registro con ubicación del caché offline.';
        setTimeout(() => error.value = null, 4000);
      }
      
    } catch (offlineError) {
      console.error('❌ Error en servicio offline para registro:', offlineError);
      
      // Último recurso para registros
      console.log('🆘 Aplicando ubicación de emergencia para registro...');
      latitudRegistro.value = 19.4326; // Ciudad de México
      longitudRegistro.value = -99.1332;
      
      error.value = 'Registro con ubicación por defecto (modo offline).';
      setTimeout(() => error.value = null, 8000);
    }
  } finally {
    obteniendoUbicacionRegistro.value = false;
  }
}

async function onFileChange(e) {
  const file = e.target.files[0];
  if (!file) return;

  // IMPORTANTE: Limpiar imagen anterior antes de procesar la nueva
  // Esto evita que queden referencias a la imagen anterior en memoria
  foto.value = null;
  archivoFoto.value = null;

  try {
    // Compresión de imagen con calidad media y formato JPG
    console.log('🖼️ Comprimiendo imagen de asistencia...');
    console.log(`📷 Archivo original: ${file.name}, tamaño: ${(file.size/1024).toFixed(2)}KB`);
    
    const compressedBlob = await compressImage(file, 1280, 0.6);
    
    // Generar nombre único con timestamp + random para evitar colisiones
    const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const compressedFile = blobToFile(compressedBlob, `${tipoAsistencia.value || 'asistencia'}_${uniqueId}.jpg`);
    
    console.log(`✅ Imagen comprimida: ${compressedFile.name}, tamaño: ${(compressedFile.size/1024).toFixed(2)}KB`);
    
    // Usar el archivo comprimido
    archivoFoto.value = compressedFile;
    
    // Mostrar la imagen comprimida en la interfaz
    const reader = new FileReader();
    reader.onload = (e2) => {
      foto.value = e2.target.result;
      console.log(`✅ Vista previa de imagen actualizada`);
    };
    reader.readAsDataURL(compressedBlob);
  } catch (err) {
    console.error('Error al comprimir imagen:', err);
    // Fallback: usar la imagen original sin comprimir
    const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    // Crear un nuevo File con nombre único para evitar caché
    const newFile = new File([file], `${tipoAsistencia.value || 'asistencia'}_${uniqueId}.jpg`, { type: file.type });
    archivoFoto.value = newFile;
    
    const reader = new FileReader();
    reader.onload = (e2) => {
      foto.value = e2.target.result;
    };
    reader.readAsDataURL(file);
  }
}

async function onFileChangeRegistro(e) {
  const file = e.target.files[0];
  if (!file) return;

  // IMPORTANTE: Limpiar imagen anterior antes de procesar la nueva
  // Esto evita que queden referencias a la imagen anterior en memoria
  fotoRegistro.value = null;
  archivoFotoRegistro.value = null;

  try {
    // Compresión de imagen con calidad media y formato JPG
    console.log('🖼️ Comprimiendo imagen de registro...');
    console.log(`📷 Archivo original: ${file.name}, tamaño: ${(file.size/1024).toFixed(2)}KB`);
    
    const compressedBlob = await compressImage(file, 1280, 0.6);
    
    // Generar nombre único con timestamp + random para evitar colisiones
    const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const compressedFile = blobToFile(compressedBlob, `actividad_${uniqueId}.jpg`);
    
    console.log(`✅ Imagen comprimida: ${compressedFile.name}, tamaño: ${(compressedFile.size/1024).toFixed(2)}KB`);
    
    // Usar el archivo comprimido
    archivoFotoRegistro.value = compressedFile;
    
    // Mostrar la imagen comprimida en la interfaz
    const reader = new FileReader();
    reader.onload = (e2) => {
      fotoRegistro.value = e2.target.result;
      console.log(`✅ Vista previa de imagen actualizada (${fotoRegistro.value.substring(0, 50)}...)`);
    };
    reader.readAsDataURL(compressedBlob);
  } catch (err) {
    console.error('Error al comprimir imagen:', err);
    // Fallback: usar la imagen original sin comprimir
    const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    // Crear un nuevo File con nombre único para evitar caché
    const newFile = new File([file], `actividad_${uniqueId}.jpg`, { type: file.type });
    archivoFotoRegistro.value = newFile;
    
    const reader = new FileReader();
    reader.onload = (e2) => {
      fotoRegistro.value = e2.target.result;
    };
    reader.readAsDataURL(file);
  }
}

// Nuevas funciones para manejo de fotos con opciones separadas

// Funciones para asistencia (entrada/salida)
function tomarFotoConCamara() {
  // IMPORTANTE: Limpiar el valor del input ANTES de abrir la cámara
  // Esto fuerza al navegador a disparar el evento @change incluso si selecciona la misma imagen
  if (fileInputCamera.value) {
    fileInputCamera.value.value = '';
    fileInputCamera.value.click();
  }
}

function seleccionarDeGaleria() {
  // IMPORTANTE: Limpiar el valor del input ANTES de abrir la galería
  // Esto fuerza al navegador a disparar el evento @change incluso si selecciona la misma imagen
  if (fileInputGallery.value) {
    fileInputGallery.value.value = '';
    fileInputGallery.value.click();
  }
}

function eliminarFoto() {
  foto.value = null;
  archivoFoto.value = null;
  
  // Limpiar ambos inputs
  if (fileInputCamera.value) {
    fileInputCamera.value.value = "";
  }
  if (fileInputGallery.value) {
    fileInputGallery.value.value = "";
  }
}

// Funciones para registro de actividades
function tomarFotoConCamaraRegistro() {
  if (!entradaMarcada.value || salidaMarcada.value) return;
  
  // IMPORTANTE: Limpiar el valor del input ANTES de abrir la cámara
  // Esto fuerza al navegador a disparar el evento @change incluso si selecciona la misma imagen
  if (fileInputCameraRegistro.value) {
    fileInputCameraRegistro.value.value = '';
    fileInputCameraRegistro.value.click();
  }
}

function seleccionarDeGaleriaRegistro() {
  if (!entradaMarcada.value || salidaMarcada.value) return;
  
  // IMPORTANTE: Limpiar el valor del input ANTES de abrir la galería
  // Esto fuerza al navegador a disparar el evento @change incluso si selecciona la misma imagen
  if (fileInputGalleryRegistro.value) {
    fileInputGalleryRegistro.value.value = '';
    fileInputGalleryRegistro.value.click();
  }
}

function eliminarFotoRegistro() {
  if (!entradaMarcada.value || salidaMarcada.value) return;
  
  fotoRegistro.value = null;
  archivoFotoRegistro.value = null;
  
  // Limpiar ambos inputs de registro
  if (fileInputCameraRegistro.value) {
    fileInputCameraRegistro.value.value = "";
  }
  if (fileInputGalleryRegistro.value) {
    fileInputGalleryRegistro.value.value = "";
  }
}

async function enviarRegistro() {
  // Verificar estado de asistencia
  if (!entradaMarcada.value) {
    error.value = "❌ Debes marcar tu entrada primero para poder registrar actividades.";
    setTimeout(() => error.value = null, 5000);
    return;
  }
  
  if (salidaMarcada.value) {
    error.value = "❌ Has marcado tu salida. No puedes registrar más actividades hoy.";
    setTimeout(() => error.value = null, 5000);
    return;
  }

  // Validación silenciosa - el indicador visual ya muestra qué falta
  // El botón está deshabilitado así que esto es solo una protección adicional
  if (!latitudRegistro.value || !longitudRegistro.value || !archivoFotoRegistro.value || !tipoActividad.value) {
    return;
  }

  // Validar categoría de actividad - protección silenciosa
  if (!categoriaActividad.value) {
    return;
  }

  // Validar campo "Otro" si está seleccionado - protección silenciosa
  if (categoriaActividad.value === 'Otro' && !categoriaActividadOtro.value.trim()) {
    return;
  }

  enviando.value = true;
  error.value = null;

  try {
    // Verificar conexión a internet antes de enviar
    isOnline.value = await checkInternetConnection();
    
    if (!isOnline.value) {
      // **MODO OFFLINE: Guardar datos localmente**
      console.log('📴 Sin conexión - Guardando registro offline');
      
      // MEJORA: Guardar con información más completa para garantizar sincronización
      const timestampCDMX = obtenerTimestampCDMX();
      const registroID = await offlineService.guardarRegistroOffline(
        user.value.id,
        latitudRegistro.value,
        longitudRegistro.value,
        descripcionRegistro.value,
        archivoFotoRegistro.value,
        tipoActividad.value, // tipo de actividad (campo/gabinete)
        timestampCDMX, // timestamp CDMX exacto
        categoriaActividad.value, // NUEVO: categoría de actividad
        categoriaActividad.value === 'Otro' ? categoriaActividadOtro.value.trim() : null // NUEVO: especificación si es "Otro"
      );
      
      console.log(`✅ Registro offline guardado con ID: ${registroID}`);
      
      // Notificar al servicio de sincronización que hay registros pendientes
      // Esto ayuda a asegurar que el sistema está consciente del nuevo registro
      syncService.notifyListeners('pending_update', false, {
        tipo: 'registro', 
        id: registroID,
        timestamp: timestampCDMX
      });
      
      // Agregar a historial local con indicador offline
      historial.value.unshift({
        fecha: new Date(timestampCDMX).toLocaleString('es-MX', {
          timeZone: 'America/Mexico_City',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        }),
        latitud: latitudRegistro.value,
        longitud: longitudRegistro.value,
        descripcion: descripcionRegistro.value,
        tipo_actividad: tipoActividad.value,
        categoria_actividad: categoriaActividad.value, // NUEVO
        categoria_actividad_otro: categoriaActividad.value === 'Otro' ? categoriaActividadOtro.value.trim() : null, // NUEVO
        foto: fotoRegistro.value,
        offline: true, // Marcador para indicar que está pendiente
        backend: null,
        tipo: 'actividad', // Especificar explícitamente el tipo de registro
        id_offline: registroID // Guardar el ID generado para referencia
      });

      // Limpiar campos
      descripcionRegistro.value = "";
      tipoActividad.value = "";
      categoriaActividad.value = ""; // NUEVO: limpiar categoría
      categoriaActividadOtro.value = ""; // NUEVO: limpiar especificación
      fotoRegistro.value = null;
      archivoFotoRegistro.value = null;
      latitudRegistro.value = null;
      longitudRegistro.value = null;

      // Limpiar todos los inputs de archivo de registro
      if (fileInputRegistro.value) {
        fileInputRegistro.value.value = "";
      }
      if (fileInputCameraRegistro.value) {
        fileInputCameraRegistro.value.value = "";
      }
      if (fileInputGalleryRegistro.value) {
        fileInputGalleryRegistro.value.value = "";
      }

      // Mostrar modal de éxito offline
      modalMessage.value = "¡Registro guardado offline! Se enviará automáticamente cuando recuperes la conexión.";
      showModal.value = true;
      
      return;
    }

    // **MODO ONLINE: Enviar directamente al servidor**
    console.log('🌐 Conexión disponible - Enviando registro al servidor');

    // Crear FormData para enviar al servidor
    const formData = new FormData();
    formData.append("usuario_id", user.value.id.toString());
    formData.append("latitud", latitudRegistro.value);
    formData.append("longitud", longitudRegistro.value);
    formData.append("descripcion", descripcionRegistro.value);
    formData.append("tipo_actividad", tipoActividad.value);
    formData.append("categoria_actividad", categoriaActividad.value); // NUEVO: categoría de actividad
    // NUEVO: solo enviar categoria_actividad_otro si la categoría es "Otro"
    if (categoriaActividad.value === 'Otro') {
      formData.append("categoria_actividad_otro", categoriaActividadOtro.value.trim());
    }
    formData.append("foto", archivoFotoRegistro.value);
    formData.append("tipo", "actividad"); // Especificar explícitamente que es un registro de actividad
    // ✅ SOLUCIÓN: Agregar SIEMPRE timestamp CDMX exacto (igual que el reloj de la barra verde)
    // El servidor SIEMPRE lo debe recibir y usarlo para garantizar fecha/hora correcta
    formData.append("timestamp_offline", obtenerTimestampCDMX());
    
    // Enviar datos al backend
    const response = await axios.post(`${API_URL}/registro`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
        "X-Registro-Tipo": "actividad" // Identificar explícitamente el tipo de registro
      },
      timeout: 15000,
      maxContentLength: Infinity,
      maxBodyLength: Infinity
    });

    // Guardar en historial local
    historial.value.unshift({
      fecha: new Date().toLocaleString(),
      latitud: latitudRegistro.value,
      longitud: longitudRegistro.value,
      descripcion: descripcionRegistro.value,
      tipo_actividad: tipoActividad.value,
      categoria_actividad: categoriaActividad.value, // NUEVO
      categoria_actividad_otro: categoriaActividad.value === 'Otro' ? categoriaActividadOtro.value.trim() : null, // NUEVO
      foto: fotoRegistro.value,
      offline: false, // Enviado exitosamente
      backend: response.data,
      tipo: 'actividad' // Especificar explícitamente el tipo de registro
    });

    // Limpiar campos
    descripcionRegistro.value = "";
    tipoActividad.value = "";
    categoriaActividad.value = ""; // NUEVO: limpiar categoría
    categoriaActividadOtro.value = ""; // NUEVO: limpiar especificación
    fotoRegistro.value = null;
    archivoFotoRegistro.value = null;
    latitudRegistro.value = null;
    longitudRegistro.value = null;

    // Limpiar todos los inputs de archivo de registro
    if (fileInputRegistro.value) {
      fileInputRegistro.value.value = "";
    }
    if (fileInputCameraRegistro.value) {
      fileInputCameraRegistro.value.value = "";
    }
    if (fileInputGalleryRegistro.value) {
      fileInputGalleryRegistro.value.value = "";
    }

    // Mostrar modal de éxito
    modalMessage.value = "¡Registro enviado y guardado correctamente!";
    showModal.value = true;
    
  } catch (err) {
    console.error("Error al enviar datos:", err);

    // Error HTTP explícito del servidor (4xx, 5xx con cuerpo)
    if (err.response) {
      error.value = "Error del servidor: " + (err.response.data?.detail || err.response.statusText);
      return;
    }

    // Cualquier otro error (red, service worker, timeout, SSL, desconocido) → guardar offline
    console.log('📴 Error de conexión en actividad, guardando offline como fallback...');
    try {
      const timestampCDMX = obtenerTimestampCDMX();
      const registroID = await offlineService.guardarRegistroOffline(
        user.value.id,
        latitudRegistro.value,
        longitudRegistro.value,
        descripcionRegistro.value,
        archivoFotoRegistro.value,
        tipoActividad.value,
        timestampCDMX,
        categoriaActividad.value,
        categoriaActividad.value === 'Otro' ? categoriaActividadOtro.value.trim() : null
      );

      historial.value.unshift({
        fecha: new Date(timestampCDMX).toLocaleString('es-MX', {
          timeZone: 'America/Mexico_City',
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit'
        }),
        latitud: latitudRegistro.value,
        longitud: longitudRegistro.value,
        descripcion: descripcionRegistro.value,
        tipo_actividad: tipoActividad.value,
        categoria_actividad: categoriaActividad.value,
        categoria_actividad_otro: categoriaActividad.value === 'Otro' ? categoriaActividadOtro.value.trim() : null,
        foto: fotoRegistro.value,
        offline: true,
        backend: null,
        tipo: 'actividad',
        id_offline: registroID
      });

      descripcionRegistro.value = "";
      tipoActividad.value = "";
      categoriaActividad.value = "";
      categoriaActividadOtro.value = "";
      fotoRegistro.value = null;
      archivoFotoRegistro.value = null;
      latitudRegistro.value = null;
      longitudRegistro.value = null;
      if (fileInputRegistro.value) fileInputRegistro.value.value = "";
      if (fileInputCameraRegistro.value) fileInputCameraRegistro.value.value = "";
      if (fileInputGalleryRegistro.value) fileInputGalleryRegistro.value.value = "";

      modalMessage.value = "¡Registro guardado! Se sincronizará automáticamente cuando el servidor esté disponible.";
      showModal.value = true;
    } catch (offlineErr) {
      console.error('Error guardando actividad offline como fallback:', offlineErr);
      error.value = "Sin conexión y no se pudo guardar localmente. Intenta de nuevo.";
    }
  } finally {
    enviando.value = false;
  }
}

function closeSuccessModal() {
  showModal.value = false;
  modalMessage.value = '';
}

// Funciones para modales de confirmación
function mostrarModalEntrada() {
  entradaModalMessage.value = `
    <div class="text-left">
      <div class="flex items-center mb-3">
        <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center mr-3" style="background-color: rgba(30, 144, 255, 0.1);">
          <svg class="w-5 h-5" style="color: rgb(30, 144, 255);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
        </div>
        <div>
          <h3 class="text-base font-semibold text-gray-900">Registro de Inicio</h3>
          <p class="text-xs text-gray-600">Inicia tu jornada laboral</p>
        </div>
      </div>
      
      <div class="p-3 mb-3 rounded" style="background-color: rgba(30, 144, 255, 0.1); border-left: 4px solid rgba(30, 144, 255, 0.6);">
        <div class="flex items-center">
          <svg class="w-4 h-4 mr-2" style="color: rgb(30, 144, 255);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <p class="font-medium text-sm" style="color: rgb(25, 118, 210);">Al registrar inicio podrás capturar actividades</p>
        </div>
        <p class="text-xs mt-1 ml-6" style="color: rgb(30, 144, 255);">Durante tu jornada podrás documentar todas tus tareas</p>
      </div>

      <div class="space-y-2 text-xs text-gray-600">
        <div class="flex items-start">
          <svg class="w-3 h-3 mr-2 mt-0.5 flex-shrink-0" style="color: rgb(30, 144, 255);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
          </svg>
          <span>Se capturará ubicación y fotografía</span>
        </div>
        
        <div class="flex items-start">
          <svg class="w-3 h-3 text-purple-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"/>
          </svg>
          <span>Funciona offline</span>
        </div>
        
        <div class="flex items-start">
          <svg class="w-3 h-3 text-amber-500 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
          </svg>
          <span>No se puede cancelar una vez registrado</span>
        </div>
      </div>
    </div>
  `;
  showEntradaModal.value = true;
}

function mostrarModalSalida() {
  salidaModalMessage.value = `
    <div class="text-left">
      <div class="flex items-center mb-3">
        <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center mr-3" style="background-color: rgba(220, 20, 60, 0.1);">
          <svg class="w-5 h-5" style="color: rgb(220, 20, 60);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
        </div>
        <div>
          <h3 class="text-base font-semibold text-gray-900">Registro de Término</h3>
          <p class="text-xs text-gray-600">Finaliza tu jornada laboral</p>
        </div>
      </div>
      
      <div class="p-3 mb-3 rounded" style="background-color: rgba(220, 20, 60, 0.1); border-left: 4px solid rgba(220, 20, 60, 0.6);">
        <div class="flex items-center">
          <svg class="w-4 h-4 mr-2" style="color: rgb(220, 20, 60);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18 21l-5.197-5.197m0 0L12 12.803m0 0L5.196 17.996M12 12.803l5.198-5.197L21 3"/>
          </svg>
          <p class="font-medium text-sm" style="color: rgb(185, 15, 50);">No podrás registrar más actividades</p>
        </div>
        <p class="text-xs mt-1 ml-6" style="color: rgb(220, 20, 60);">El registro se bloqueará hasta mañana</p>
      </div>

      <div class="space-y-3 text-sm text-gray-600">
        <div class="flex items-start">
          <svg class="w-4 h-4 mr-3 mt-0.5 flex-shrink-0" style="color: rgb(220, 20, 60);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
          </svg>
          <span>Se capturará tu ubicación actual y una fotografía</span>
        </div>
        
        <div class="flex items-start">
          <svg class="w-4 h-4 text-purple-500 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"/>
          </svg>
          <span>Funciona sin conexión (se sincroniza automáticamente)</span>
        </div>
        
        <div class="flex items-start">
          <svg class="w-4 h-4 text-amber-500 mr-3 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
          </svg>
          <span>Una vez registrada no se puede cancelar</span>
        </div>
      </div>
    </div>
  `;
  showSalidaModal.value = true;
}

function closeEntradaModal() {
  showEntradaModal.value = false;
  entradaModalMessage.value = '';
}

function closeSalidaModal() {
  showSalidaModal.value = false;
  salidaModalMessage.value = '';
}

function confirmarEntradaModal() {
  closeEntradaModal();
  iniciarAsistencia('entrada');
}

function confirmarSalidaModal() {
  closeSalidaModal();
  iniciarAsistencia('salida');
}

function mostrarModalActividadesBloqueadas() {
  if (!entradaMarcada.value) {
    actividadesBloqueadasModalMessage.value = `
      <div class="text-center px-2">
        <!-- Icono principal con animación -->
        <div class="flex justify-center mb-4">
          <div class="w-16 h-16 bg-gradient-to-br from-slate-700 to-slate-900 rounded-2xl flex items-center justify-center shadow-xl transform rotate-3">
            <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
          </div>
        </div>
        
        <!-- Título -->
        <h3 class="text-lg font-bold text-slate-800 mb-2">Acceso Restringido</h3>
        
        <!-- Mensaje principal -->
        <div class="bg-gradient-to-r from-slate-100 to-gray-100 border-l-4 border-slate-600 rounded-r-xl p-4 mb-4 shadow-sm">
          <p class="text-slate-700 text-sm font-semibold mb-1">Registra tu inicio de jornada</p>
          <p class="text-slate-500 text-xs">Presiona "Registro de Inicio" en la sección de Registro para habilitar el registro de actividades</p>
        </div>
        
        <!-- Pasos -->
        <div class="flex items-center justify-center space-x-2 text-xs text-slate-500">
          <span class="flex items-center bg-slate-200 px-3 py-1.5 rounded-full">
            <span class="w-5 h-5 bg-slate-600 text-white rounded-full flex items-center justify-center text-xs font-bold mr-2">1</span>
            Inicio
          </span>
          <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
          <span class="flex items-center bg-slate-100 px-3 py-1.5 rounded-full text-slate-400">
            <span class="w-5 h-5 bg-slate-300 text-slate-500 rounded-full flex items-center justify-center text-xs font-bold mr-2">2</span>
            Actividades
          </span>
        </div>
      </div>
    `;
  } else if (salidaMarcada.value) {
    actividadesBloqueadasModalMessage.value = `
      <div class="text-center px-2">
        <!-- Icono principal -->
        <div class="flex justify-center mb-4">
          <div class="w-16 h-16 bg-gradient-to-br from-gray-600 to-gray-800 rounded-2xl flex items-center justify-center shadow-xl transform -rotate-3">
            <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </div>
        </div>
        
        <!-- Título -->
        <h3 class="text-lg font-bold text-gray-800 mb-2">Jornada Finalizada</h3>
        
        <!-- Mensaje principal -->
        <div class="bg-gradient-to-r from-gray-100 to-slate-100 border-l-4 border-gray-500 rounded-r-xl p-4 mb-4 shadow-sm">
          <p class="text-gray-700 text-sm font-semibold mb-1">Término de jornada registrado</p>
          <p class="text-gray-500 text-xs">El acceso a actividades se restablecerá automáticamente mañana con un nuevo registro de inicio</p>
        </div>
        
        <!-- Estado -->
        <div class="inline-flex items-center bg-gray-200 px-4 py-2 rounded-full">
          <div class="w-2 h-2 bg-gray-500 rounded-full mr-2 animate-pulse"></div>
          <span class="text-xs font-medium text-gray-600">Esperando próximo día</span>
        </div>
      </div>
    `;
  }
  
  showActividadesBloqueadasModal.value = true;
}

function closeActividadesBloqueadasModal() {
  showActividadesBloqueadasModal.value = false;
  actividadesBloqueadasModalMessage.value = '';
}

function verificarEstadoAsistencia() {
  try {
    // *** CORREGIDO: Usar fecha CDMX consistente ***
    const fechaHoyCDMX = new Date().toLocaleString("en-CA", {
      timeZone: "America/Mexico_City",
      year: "numeric",
      month: "2-digit", 
      day: "2-digit"
    });
    
    console.log(`🔍 Verificando estado de asistencia para ${fechaHoyCDMX}`);
    
    // Reiniciar estados por defecto (suponemos que no hay registros)
    entradaMarcada.value = false;
    salidaMarcada.value = false;
    datosEntrada.value = {};
    datosSalida.value = {};
    
    // Verificamos si hay datos guardados para el día de hoy específicamente
    const estadoHoy = localStorage.getItem(`asistencia_${user.value.id}_${fechaHoyCDMX}`);
    
    if (estadoHoy) {
      const datos = JSON.parse(estadoHoy);
      
      // *** CORREGIDO: Verificar expiración en zona horaria CDMX ***
      const ahoraCDMX = new Date().toLocaleString("sv-SE", { timeZone: "America/Mexico_City" });
      const fechaCompletaCDMX = new Date(ahoraCDMX);
      
      const expiraEn = datos.expiraEn ? new Date(datos.expiraEn) : new Date(fechaHoyCDMX + 'T23:59:59');
      const esValido = fechaCompletaCDMX < expiraEn;
      
      console.log(`📊 Datos locales encontrados para hoy:`, {
        entrada: !!datos.entradaMarcada,
        salida: !!datos.salidaMarcada,
        expiraEn: expiraEn.toLocaleString("es-MX", { timeZone: "America/Mexico_City" }),
        esValido,
        horaActualCDMX: fechaCompletaCDMX.toLocaleString("es-MX", { timeZone: "America/Mexico_City" })
      });
      
      if (esValido) {
        // Los datos son válidos (todavía estamos en el mismo día antes de las 23:59:59 CDMX)
        console.log(`✅ Usando datos locales válidos (expiran a las 23:59:59 CDMX)`);
        entradaMarcada.value = datos.entradaMarcada || false;
        salidaMarcada.value = datos.salidaMarcada || false;
        datosEntrada.value = datos.datosEntrada || {};
        datosSalida.value = datos.datosSalida || {};
      } else {
        console.log(`⚠️ Datos locales expirados, reiniciando estados`);
      }
    } else {
      console.log(`ℹ️ No hay datos guardados para hoy, consultando backend`);
    }

    // Limpiamos datos de días anteriores para no acumular basura en localStorage
    limpiarDatosAntiguos();

    // Después de cargar del localStorage, verificar con el backend para tener datos actualizados
    verificarAsistenciaHoy();
  } catch (error) {
    console.error('Error al verificar estado de asistencia:', error);
  }
}

// Función para asegurar que los estados se mantengan correctamente hasta las 23:59:59 CDMX
function asegurarEstadosConsistentes() {
  if (!user.value.id) return;
  
  // *** CORREGIDO: Usar fecha CDMX consistente ***
  const fechaHoyCDMX = new Date().toLocaleString("en-CA", {
    timeZone: "America/Mexico_City",
    year: "numeric",
    month: "2-digit", 
    day: "2-digit"
  });
  
  console.log('🔐 Verificando consistencia de estados de asistencia...');
  
  try {
    const estadoHoy = localStorage.getItem(`asistencia_${user.value.id}_${fechaHoyCDMX}`);
    
    if (estadoHoy) {
      const datos = JSON.parse(estadoHoy);
      
      // *** CORREGIDO: Verificar expiración en zona horaria CDMX ***
      const ahoraCDMX = new Date().toLocaleString("sv-SE", { timeZone: "America/Mexico_City" });
      const fechaCompletaCDMX = new Date(ahoraCDMX);
      
      const expiraEn = datos.expiraEn ? new Date(datos.expiraEn) : new Date(fechaHoyCDMX + 'T23:59:59');
      
      if (fechaCompletaCDMX < expiraEn) {
        console.log('✅ Asegurando estados hasta las 23:59:59 CDMX');
        
        // Si en localStorage indica que la entrada fue marcada, asegurar que se refleje en el estado
        if (datos.entradaMarcada && !entradaMarcada.value) {
          console.log('🔄 Restaurando estado de entrada marcada');
          entradaMarcada.value = true;
          datosEntrada.value = datos.datosEntrada || {};
        }
        
        // Si en localStorage indica que la salida fue marcada, asegurar que se refleje en el estado
        if (datos.salidaMarcada && !salidaMarcada.value) {
          console.log('🔄 Restaurando estado de salida marcada');
          salidaMarcada.value = true;
          datosSalida.value = datos.datosSalida || {};
        }
      }
    }
  } catch (error) {
    console.error('❌ Error al asegurar estados consistentes:', error);
  }
}

/**
 * Limpia los datos de asistencia de días anteriores del localStorage
 */
function limpiarDatosAntiguos() {
  try {
    // *** CORREGIDO: Usar fecha CDMX consistente ***
    const hoyCDMX = new Date().toLocaleString("en-CA", {
      timeZone: "America/Mexico_City",
      year: "numeric",
      month: "2-digit", 
      day: "2-digit"
    });
    
    // Recorremos todas las claves del localStorage
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      
      // Si es una clave de asistencia para este usuario pero no de hoy, la eliminamos
      if (key && key.startsWith(`asistencia_${user.value.id}_`) && !key.includes(hoyCDMX)) {
        localStorage.removeItem(key);
        console.log(`🧹 Eliminando datos antiguos: ${key}`);
      }
    }
  } catch (error) {
    console.error('Error al limpiar datos antiguos:', error);
  }
}

/**
 * Consulta al backend si el usuario ya registró entrada/salida hoy
 */
  async function verificarAsistenciaHoy(forceRefresh = false) {
    verificandoAsistencia.value = true;
    try {
      // Verificar conexión a internet antes de consultar
      isOnline.value = await checkInternetConnection();
      if (!isOnline.value) {
        console.log('Sin conexión, usando datos locales de asistencia');
        return;
      }

      // *** CORREGIDO: Obtener fecha actual en zona horaria de CDMX ***
      const ahoraCDMX = new Date().toLocaleString("en-CA", {
        timeZone: "America/Mexico_City",
        year: "numeric",
        month: "2-digit", 
        day: "2-digit"
      });
      const fechaActual = ahoraCDMX; // Formato YYYY-MM-DD en CDMX
      
      console.log(`🔍 Consultando asistencia del día con forceRefresh=${forceRefresh}`);
      console.log(`📅 Fecha actual CDMX: ${fechaActual}`);
      const datos = await asistenciasService.consultarAsistenciaHoy(user.value.id, forceRefresh);
      asistenciaHoy.value = datos;
      
      console.log(`📊 Datos recibidos del backend - fecha: ${datos.fecha}, entrada: ${!!datos.entrada}, salida: ${!!datos.salida}`);
      
      // Verificar que los datos correspondan al día actual EN ZONA CDMX
      if (datos.fecha && datos.fecha === fechaActual) {
        // Actualizar estado de botones según la respuesta del backend
        if (datos.entrada) {
          entradaMarcada.value = true;
          datosEntrada.value = {
            hora: formatearHora(datos.entrada),
            descripcion: datos.descripcion_entrada || '',
            latitud: datos.latitud_entrada,
            longitud: datos.longitud_entrada,
            foto_url: datos.foto_entrada_url
          };
        } else {
          // Si no hay entrada registrada hoy, resetear estado
          entradaMarcada.value = false;
          datosEntrada.value = {};
        }
        
        if (datos.salida) {
          salidaMarcada.value = true;
          datosSalida.value = {
            hora: formatearHora(datos.salida),
            descripcion: datos.descripcion_salida || '',
            latitud: datos.latitud_salida,
            longitud: datos.longitud_salida,
            foto_url: datos.foto_salida_url
          };
        } else {
          // Si no hay salida registrada hoy, resetear estado de salida
          salidaMarcada.value = false;
          datosSalida.value = {};
        }
        
        // Guardar estado actualizado
        guardarEstadoAsistencia();
        
        console.log(`✅ Estados actualizados para fecha ${fechaActual}: entrada=${entradaMarcada.value}, salida=${salidaMarcada.value}`);
      } else {
        console.log(`ℹ️ Fecha del backend (${datos.fecha}) ≠ fecha actual CDMX (${fechaActual})`);
        
        // *** CORREGIDO: Solo reiniciar estados si realmente es un día diferente ***
        // Verificar si realmente es un nuevo día comparando fechas correctamente
        const fechaGuardadaLocal = localStorage.getItem(`asistencia_ultima_fecha_${user.value.id}`);
        
        if (fechaGuardadaLocal !== fechaActual) {
          console.log(`📆 Nuevo día detectado (guardado: ${fechaGuardadaLocal}, actual: ${fechaActual}). Reiniciando estados.`);
          // Es realmente un nuevo día, reiniciar estados
          entradaMarcada.value = false;
          salidaMarcada.value = false;
          datosEntrada.value = {};
          datosSalida.value = {};
          guardarEstadoAsistencia();
        } else {
          console.log(`⚠️ Manteniendo estados actuales - posible diferencia de zona horaria entre frontend y backend`);
          // No reiniciar estados si el día guardado coincide con el actual
        }
      }
    } catch (error) {
      console.error('Error al verificar asistencia de hoy:', error);
      // *** CORREGIDO: Solo reiniciar estados en caso de verdadero cambio de día ***
      const fechaGuardada = localStorage.getItem(`asistencia_ultima_fecha_${user.value.id}`);
      
      // Obtener fecha actual CDMX correctamente
      const fechaActualCDMX = new Date().toLocaleString("en-CA", {
        timeZone: "America/Mexico_City",
        year: "numeric",
        month: "2-digit", 
        day: "2-digit"
      });
      
      if (fechaGuardada !== fechaActualCDMX) {
        console.log(`📆 Nuevo día detectado durante error (guardado: ${fechaGuardada}, actual: ${fechaActualCDMX}). Reiniciando estados.`);
        // Es un nuevo día, reiniciar estados incluso sin conexión
        entradaMarcada.value = false;
        salidaMarcada.value = false;
        datosEntrada.value = {};
        datosSalida.value = {};
        guardarEstadoAsistencia();
      } else {
        console.log(`⚠️ Error de conexión, pero manteniendo estados del mismo día (${fechaActualCDMX})`);
      }
    } finally {
      verificandoAsistencia.value = false;
    }
  }/**
 * Formatea una fecha ISO a formato de hora local
 */
function formatearHora(fechaISO) {
  if (!fechaISO) return "";
  const hora = new Date(fechaISO);
  return hora.toLocaleTimeString("es-MX", { hour: '2-digit', minute: '2-digit', timeZone: 'America/Mexico_City' });
}

function guardarEstadoAsistencia() {
  // *** CORREGIDO: Usar fecha CDMX consistente ***
  const fechaHoyCDMX = new Date().toLocaleString("en-CA", {
    timeZone: "America/Mexico_City",
    year: "numeric",
    month: "2-digit", 
    day: "2-digit"
  });
  
  // Configurar expiración a las 23:59:59 del día actual EN CDMX
  const ahoraCDMX = new Date().toLocaleString("sv-SE", { timeZone: "America/Mexico_City" });
  const fechaCompletaCDMX = new Date(ahoraCDMX);
  const finDelDiaCDMX = new Date(fechaCompletaCDMX);
  finDelDiaCDMX.setHours(23, 59, 59, 999);
  
  const estado = {
    entradaMarcada: entradaMarcada.value,
    salidaMarcada: salidaMarcada.value,
    datosEntrada: datosEntrada.value,
    datosSalida: datosSalida.value,
    ultimaActualizacion: new Date().toISOString(),
    // Guardar hora de expiración a las 23:59:59 del día actual EN CDMX
    expiraEn: finDelDiaCDMX.toISOString()
  };
  
  console.log(`💾 Guardando estado de asistencia para el día ${fechaHoyCDMX}`);
  console.log(`   ⏰ Entrada marcada: ${entradaMarcada.value}`);
  console.log(`   ⏰ Salida marcada: ${salidaMarcada.value}`);
  console.log(`   📅 Expira a las: ${finDelDiaCDMX.toLocaleString("es-MX", { timeZone: "America/Mexico_City" })} (23:59:59 CDMX)`);
  
  // Guardar el estado del día actual
  localStorage.setItem(`asistencia_${user.value.id}_${fechaHoyCDMX}`, JSON.stringify(estado));
  
  // También guardar la última fecha consultada para comparaciones EN CDMX
  localStorage.setItem(`asistencia_ultima_fecha_${user.value.id}`, fechaHoyCDMX);
}

/**
 * Carga los registros de actividades para el historial
 * @param {boolean} forceRefresh - Si es true, fuerza una actualización desde el servidor
 */
async function cargarHistorial(forceRefresh = false) {
  try {
    console.log(`🔄 Cargando historial de registros${forceRefresh ? ' (forzando actualización)' : ''}...`);
    
    // Verificar conexión a internet
    const isConnected = await checkInternetConnection();
    if (!isConnected) {
      console.log('📴 Sin conexión, mostrando solo registros offline');
      // Mostrar registros offline si hay
      const pendientes = await offlineService.obtenerResumenPendientes();
      if (pendientes && pendientes.registros && pendientes.registros.items) {
        historial.value = pendientes.registros.items.map(r => ({
          fecha: new Date(r.timestamp).toLocaleString(),
          latitud: r.latitud,
          longitud: r.longitud,
          descripcion: r.descripcion || 'Sin descripción',
          offline: true,
          tipo: r.tipo || 'actividad'
        }));
      }
      return;
    }
    
    // Si hay conexión, intentar obtener del servidor
    // Siempre incluir un parámetro de tiempo para forzar nueva petición sin cache
    const cacheParam = `&_nocache=${Date.now()}`;
    const response = await axios.get(
      `${API_URL}/registros?usuario_id=${user.value.id}${cacheParam}`, 
      {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'X-Force-Refresh': 'true'
        }
      }
    );
    
    // Procesamos los registros del servidor
    // El backend responde { registros: [...], total, page, page_size }, no un arreglo plano
    const registrosOnline = (response.data?.registros || []).map(r => ({
      fecha: new Date(r.timestamp).toLocaleString(),
      latitud: r.latitud,
      longitud: r.longitud,
      descripcion: r.descripcion || 'Sin descripción',
      foto: r.foto_url,
      offline: false,
      backend: r,
      tipo: r.tipo || 'actividad'
    }));
    
    // Obtenemos registros pendientes offline
    const pendientes = await offlineService.obtenerResumenPendientes();
    let registrosOffline = [];
    
    if (pendientes && pendientes.registros && pendientes.registros.items) {
      registrosOffline = pendientes.registros.items.map(r => ({
        fecha: new Date(r.timestamp).toLocaleString(),
        latitud: r.latitud,
        longitud: r.longitud,
        descripcion: r.descripcion || 'Sin descripción',
        offline: true,
        tipo: r.tipo || 'actividad'
      }));
    }
    
    // Combinar registros online y offline, los offline primero
    historial.value = [...registrosOffline, ...registrosOnline];
    
    // Ordenar por fecha más reciente primero
    historial.value.sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
    
    console.log(`✅ Historial actualizado: ${historial.value.length} registros (${registrosOffline.length} offline, ${registrosOnline.length} online)`);
    
  } catch (error) {
    console.error('❌ Error cargando historial:', error);
    // En caso de error, intentar mostrar datos offline
    try {
      const pendientes = await offlineService.obtenerResumenPendientes();
      if (pendientes && pendientes.registros && pendientes.registros.items) {
        historial.value = pendientes.registros.items.map(r => ({
          fecha: new Date(r.timestamp).toLocaleString(),
          latitud: r.latitud,
          longitud: r.longitud,
          descripcion: r.descripcion || 'Sin descripción',
          offline: true,
          tipo: r.tipo || 'actividad'
        }));
      }
    } catch (err) {
      console.error('Error cargando datos offline:', err);
    }
  }
}

// Forzar sincronización manual
async function forzarSincronizacion() {
  try {
    isOnline.value = await checkInternetConnection();
    if (!isOnline.value) {
      error.value = "No hay conexión a internet para sincronizar.";
      return;
    }
    
    console.log('🔄 Forzando sincronización manual');
    const resultado = await syncService.sincronizarManual();
    
    // Mostrar mensaje de sincronización en progreso
    mensajeAsistencia.value = "Sincronización en progreso...";
    
    // Esperar un poco para que el backend procese los datos y luego actualizar el historial
    setTimeout(async () => {
      try {
        // Forzar actualización del historial después de sincronizar
        await cargarHistorial(true);
        console.log('✅ Historial actualizado después de sincronización manual');
        
        // Verificar asistencia y actualizar UI
        await verificarAsistenciaHoy(true);
        
        // Mostrar mensaje de éxito
        if (resultado && resultado.exitosos > 0) {
          mensajeAsistencia.value = `Sincronización exitosa. ${resultado.exitosos} registro(s) enviado(s).`;
        } else {
          mensajeAsistencia.value = "Sincronización completada. No había registros pendientes.";
        }
        
        // Limpiar mensaje después de un tiempo
        setTimeout(() => {
          mensajeAsistencia.value = '';
        }, 5000);
        
      } catch (err) {
        console.error('Error actualizando historial después de sincronización manual:', err);
        mensajeAsistencia.value = "Error al actualizar registros después de sincronizar.";
      }
    }, 2000);
    
  } catch (error) {
    console.error('Error al forzar sincronización:', error);
    error.value = `Error al sincronizar: ${error.message}`;
    mensajeAsistencia.value = "Error en la sincronización.";
  }
}

// Manejador de eventos de sincronización
function handleSyncEvent(event, online, data) {
  console.log(`🔄 Evento de sincronización recibido: ${event}`);
  
  // Actualizar estado de conexión
  isOnline.value = online;
  
  switch (event) {
    case 'online':
      console.log('🌐 Conectado en Home.vue');
      error.value = null;
      
      // MEJORA: Verificar pendientes y sincronizar de manera más robusta
      // Al recuperar conexión, siempre verificar ambos tipos de pendientes (registros y asistencias)
      offlineService.contarPendientes(true).then(async pendientes => {
        console.log(`📊 Estado de pendientes al recuperar conexión:`, pendientes);
        
        // Si hay pendientes, mostrar más detalles para debugging
        if (pendientes.total > 0) {
          console.log(`🔄 Conexión recuperada con ${pendientes.total} pendientes (${pendientes.registros} registros, ${pendientes.asistencias} asistencias), sincronizando automáticamente...`);
          
          // Verificar los registros pendientes con más detalle
          if (pendientes.registros > 0) {
            // Solicitar detalle de registros pendientes para debugging
            const registrosPendientes = await offlineService.obtenerRegistrosPendientes(true);
            console.log(`🧪 DEBUGGING - Registros pendientes encontrados: ${registrosPendientes.length}`);
          }
          
          // Mostrar un mensaje informativo sobre la sincronización automática
          mensajeAsistencia.value = `Sincronizando ${pendientes.total} registro(s) pendiente(s)...`;
          
          // MEJORA: Usar un tiempo de espera mayor para asegurar conexión estable
          setTimeout(() => {
            // Usar sincronizarTodo directamente para asegurar sincronización completa
            syncService.sincronizarTodo()
              .then(resultado => {
                console.log('✅ Resultado de sincronización:', resultado);
                if (resultado.exitosos > 0) {
                  mensajeAsistencia.value = `Sincronización exitosa. ${resultado.exitosos} registro(s) enviado(s).`;
                } else if (resultado.fallidos > 0) {
                  mensajeAsistencia.value = `Sincronización parcial. ${resultado.fallidos} registro(s) con error.`;
                }
                
                // Verificar nuevamente el estado de pendientes después de sincronizar
                setTimeout(async () => {
                  const pendientesDespues = await offlineService.contarPendientes(true);
                  console.log('📊 Estado de pendientes después de sincronización:', pendientesDespues);
                }, 1000);
              })
              .catch(err => {
                console.error('❌ Error en sincronización automática al recuperar conexión:', err);
                mensajeAsistencia.value = "Error al sincronizar. Intente nuevamente.";
                setTimeout(() => {
                  mensajeAsistencia.value = '';
                }, 5000);
              });
          }, 2500); // Esperar un poco más para asegurar conexión estable
        } else {
          console.log('✅ No hay pendientes que sincronizar al recuperar conexión');
          // No mostrar mensaje si no hay pendientes
        }
      }).catch(err => {
        console.error('❌ Error verificando pendientes al recuperar conexión:', err);
      });
      break;
      
    case 'offline':
      console.log('📴 Desconectado en Home.vue');
      error.value = getOfflineMessage();
      break;
      
    case 'syncing':
      console.log('🔄 Sincronizando...');
      // Mostrar mensaje de sincronización en progreso
      mensajeAsistencia.value = "Sincronizando datos pendientes...";
      break;
      
    case 'sync_complete':
      console.log('✅ Sincronización completada:', data);
      
      // MEJORA: Verificar si hay más pendientes después de la sincronización
      offlineService.contarPendientes(true).then(pendientesDespues => {
        console.log('📊 Pendientes después de sincronización:', pendientesDespues);
        
        // Si todavía hay pendientes después de la sincronización, puede ser un problema
        if (pendientesDespues.total > 0) {
          console.warn(`⚠️ Todavía quedan ${pendientesDespues.total} registros pendientes después de sincronizar`);
          
          // Intentar un segundo ciclo de sincronización para registros difíciles
          if (data && data.exitosos > 0) {
            console.log('🔄 Intentando un segundo ciclo de sincronización para registros persistentes...');
            setTimeout(() => {
              syncService.sincronizarTodo();
            }, 5000); // Esperar 5 segundos antes de reintentar
          }
        }
      });
      
      // MEJORA: Siempre actualizar los datos después de una sincronización, incluso si no hay exitosos
      // Esto ayuda a mantener la UI siempre actualizada
      setTimeout(async () => {
        try {
          console.log('🔄 Actualizando datos después de sincronización');
          
          // Primero actualizar datos de asistencia
          await verificarAsistenciaHoy(true);
          
          // Luego actualizar el historial completo
          await cargarHistorial(true);
          
          // Mostrar mensaje de éxito según los resultados
          if (data && data.exitosos > 0) {
            mensajeAsistencia.value = `Sincronización exitosa. ${data.exitosos} registro(s) enviado(s).`;
          } else if (data && data.fallidos > 0) {
            mensajeAsistencia.value = `Hubo problemas al sincronizar ${data.fallidos} registro(s). Se reintentará automáticamente.`;
          } else {
            // Comprobar si realmente no había registros o si hubo un problema
            offlineService.contarPendientes(true).then(pendientesActuales => {
              if (pendientesActuales.total > 0) {
                mensajeAsistencia.value = `Atención: Hay ${pendientesActuales.total} registro(s) pendiente(s) que no se pudieron sincronizar.`;
              } else {
                mensajeAsistencia.value = "Sincronización completada. No había registros pendientes.";
              }
            });
          }
          
          // Limpiar mensaje después de un tiempo
          setTimeout(() => {
            mensajeAsistencia.value = '';
          }, 8000); // Aumentar tiempo de visualización
          
        } catch (error) {
          console.error('❌ Error actualizando datos después de sincronización:', error);
          mensajeAsistencia.value = "Error actualizando datos después de sincronizar.";
          setTimeout(() => {
            mensajeAsistencia.value = '';
          }, 5000);
        }
      }, 2000); // Esperar 2 segundos para dar tiempo al backend
      break;
      
    case 'sync_error':
      console.log('❌ Error en sincronización:', data);
      // Mostrar mensaje de error
      mensajeAsistencia.value = "Error en la sincronización.";
      setTimeout(() => {
        mensajeAsistencia.value = '';
      }, 5000);
      break;
  }
}

// Añadir una verificación periódica para asegurar que el estado de los botones se mantenga consistente
let verificacionPeriodica;

// Comprobación si un horario está dentro del día actual (antes de las 23:59:59 CDMX)
function esHorarioDentroDelDiaActual() {
  // *** CORREGIDO: Usar zona horaria CDMX consistente ***
  const ahoraCDMX = new Date().toLocaleString("sv-SE", { timeZone: "America/Mexico_City" });
  const fechaCompletaCDMX = new Date(ahoraCDMX);
  
  const finDelDiaCDMX = new Date(fechaCompletaCDMX);
  finDelDiaCDMX.setHours(23, 59, 59, 999);
  
  const horaActualCDMX = fechaCompletaCDMX.toLocaleString("es-MX", { timeZone: "America/Mexico_City" });
  const finDelDiaTexto = finDelDiaCDMX.toLocaleString("es-MX", { timeZone: "America/Mexico_City" });
  
  console.log(`⏰ Verificación de horario CDMX: ${horaActualCDMX} < ${finDelDiaTexto} = ${fechaCompletaCDMX < finDelDiaCDMX}`);
  
  return fechaCompletaCDMX < finDelDiaCDMX;
}

onMounted(async () => {
  // Verificar si el usuario está autenticado
  if (!user.value.id) {
    router.push("/login");
    return;
  }
  
  // *** DEBUGGING: Hacer función disponible globalmente ***
  if (typeof window !== 'undefined') {
    window.debugAsistencia = debugEstadoAsistencia;
    console.log('🔬 Función de debugging disponible: window.debugAsistencia()');
  }
  
  // Registrar manejador de eventos de sincronización
  syncService.addListener(handleSyncEvent);
  
  console.log('🚀 Inicializando componente Home, verificando estado de asistencia');
  
  // Verificar estado de asistencia del día inmediatamente
  verificarEstadoAsistencia();
  
  // Verificar conexión a internet
  isOnline.value = await checkInternetConnection();
  if (!isOnline.value) {
    error.value = getOfflineMessage();
  }
  
  // Cargar historial de registros
  cargarHistorial();
  
  // Verificar estado del servicio de geolocalización
  console.log('🔍 Verificando servicio de geolocalización...');
  try {
    const geoStatus = geoLocationService.getStatus();
    console.log('📊 Estado del servicio de geolocalización:', geoStatus);
    
    // Pre-cargar ubicación de manera silenciosa en segundo plano
    console.log('🌍 Pre-cargando ubicación en segundo plano...');
    setTimeout(async () => {
      try {
        await geoLocationService.getLocationSmart({
          timeout: 15000,
          enableHighAccuracy: true,
          useCache: true
        });
        console.log('✅ Ubicación pre-cargada exitosamente');
      } catch (error) {
        console.log('⚠️ No se pudo pre-cargar ubicación:', error.message);
        // Establecer ubicación por defecto si no se puede obtener
        geoLocationService.setDefaultLocation();
      }
    }, 2000); // Esperar 2 segundos antes de pre-cargar
    
  } catch (error) {
    console.error('❌ Error verificando servicio de geolocalización:', error);
  }
  
  // Realizar una verificación inicial de consistencia
  asegurarEstadosConsistentes();
  
  // *** NUEVA FUNCIÓN DE DEBUGGING MEJORADA ***
  async function debugEstadoAsistencia() {
    console.log('🔬 === DEBUGGING COMPLETO ESTADO ASISTENCIA ===');
    
    // 1. Información de tiempo actual
    const fechaHoyCDMX = new Date().toLocaleString("en-CA", {
      timeZone: "America/Mexico_City",
      year: "numeric",
      month: "2-digit", 
      day: "2-digit"
    });
    
    const ahoraCDMX = new Date().toLocaleString("sv-SE", { timeZone: "America/Mexico_City" });
    const fechaCompletaCDMX = new Date(ahoraCDMX);
    
    console.log('📅 Tiempo actual:');
    console.log(`   🇲🇽 Fecha CDMX: ${fechaHoyCDMX}`);
    console.log(`   ⏰ Hora completa CDMX: ${fechaCompletaCDMX.toLocaleString("es-MX", { timeZone: "America/Mexico_City" })}`);
    
    // 2. Estado actual de variables reactivas
    console.log('📊 Estado actual variables:');
    console.log(`   ✅ entradaMarcada: ${entradaMarcada.value}`);
    console.log(`   🚪 salidaMarcada: ${salidaMarcada.value}`);
    console.log(`   📝 datosEntrada:`, datosEntrada.value);
    console.log(`   📝 datosSalida:`, datosSalida.value);
    
    // 3. Estado localStorage
    const estadoHoy = localStorage.getItem(`asistencia_${user.value.id}_${fechaHoyCDMX}`);
    console.log('💾 Estado localStorage:');
    if (estadoHoy) {
      const datos = JSON.parse(estadoHoy);
      console.log(`   📦 Datos guardados para hoy:`, datos);
      
      const expiraEn = datos.expiraEn ? new Date(datos.expiraEn) : null;
      if (expiraEn) {
        console.log(`   ⏰ Expira en: ${expiraEn.toLocaleString("es-MX", { timeZone: "America/Mexico_City" })}`);
        console.log(`   ✅ Es válido: ${fechaCompletaCDMX < expiraEn}`);
      }
    } else {
      console.log('   ❌ No hay datos guardados para hoy');
    }
    
    // 4. Consultar backend
    try {
      console.log('🌐 Consultando backend...');
      const datosBackend = await asistenciasService.consultarAsistenciaHoy(user.value.id, true);
      console.log('📊 Respuesta del backend:', datosBackend);
    } catch (error) {
      console.error('❌ Error consultando backend:', error);
    }
    
    console.log('🔬 === FIN DEBUGGING ===');
  }
  
  // Realizar verificación periódica del estado de asistencia
  // Esta verificación asegura que los estados se mantengan correctos durante todo el día
  // *** CORREGIDO: Verificación menos frecuente y más inteligente ***
  // Esta verificación asegura que los estados se mantengan correctos durante todo el día
  verificacionPeriodica = setInterval(() => {
    console.log('🔄 Verificación periódica de estado de asistencia');
    // Verificar si todavía estamos en el mismo día (antes de 23:59:59 CDMX)
    if (esHorarioDentroDelDiaActual()) {
      // Asegurar consistencia local primero
      asegurarEstadosConsistentes();
      
      // *** CORREGIDO: Solo verificar con backend ocasionalmente para evitar resets ***
      // Estamos en el mismo día, verificar estados con backend solo si hay conexión
      // y sin forceRefresh para evitar problemas de sincronización
      if (navigator.onLine) {
        console.log('🔄 Verificación suave de estados con backend (sin forceRefresh)');
        verificarAsistenciaHoy(false); // *** IMPORTANTE: false para no forzar reset ***
      } else {
        console.log('📴 Sin conexión, manteniendo estados actuales');
      }
    } else {
      console.log('📆 Día finalizado (después de 23:59:59 CDMX), esperando cambio de fecha');
    }
  }, 10 * 60 * 1000); // *** CORREGIDO: Verificar cada 10 minutos en lugar de 3 ***
});

// Limpiar recursos al desmontar el componente
onUnmounted(() => {
  syncService.removeListener(handleSyncEvent);
  
  // Limpiar verificación periódica
  if (verificacionPeriodica) {
    clearInterval(verificacionPeriodica);
    console.log('🧹 Limpiado intervalo de verificación de asistencia');
  }
});

// Watcher para guardar cambios de asistencia en localStorage
watch([entradaMarcada, salidaMarcada, datosEntrada, datosSalida], () => {
  if (user.value.id) {
    guardarEstadoAsistencia();
    // Asegurar consistencia después de guardar
    asegurarEstadosConsistentes();
  }
}, { deep: true });

// Watcher para limpiar campos de registro cuando se bloquean las actividades
watch([entradaMarcada, salidaMarcada], () => {
  // Si las actividades se bloquean (no hay entrada o hay salida), limpiar campos de actividades
  if (!entradaMarcada.value || salidaMarcada.value) {
    console.log('🚫 Actividades bloqueadas, limpiando campos de registro');
    descripcionRegistro.value = "";
    tipoActividad.value = "";
    categoriaActividad.value = ""; // NUEVO: limpiar categoría
    categoriaActividadOtro.value = ""; // NUEVO: limpiar especificación
    fotoRegistro.value = null;
    archivoFotoRegistro.value = null;
    latitudRegistro.value = null;
    longitudRegistro.value = null;
    
    // Limpiar todos los inputs de archivo de registro
    if (fileInputRegistro.value) {
      fileInputRegistro.value.value = "";
    }
    if (fileInputCameraRegistro.value) {
      fileInputCameraRegistro.value.value = "";
    }
    if (fileInputGalleryRegistro.value) {
      fileInputGalleryRegistro.value.value = "";
    }
  }
});
</script>

<style scoped>
/* Animaciones de burbujas de vidrio flotantes */
@keyframes bubble-float-1 {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  10% {
    opacity: 0.6;
  }
  90% {
    opacity: 0.6;
  }
  100% {
    transform: translateY(-250px) scale(1.1);
    opacity: 0;
  }
}

@keyframes bubble-float-2 {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  15% {
    opacity: 0.5;
  }
  85% {
    opacity: 0.5;
  }
  100% {
    transform: translateY(-280px) scale(0.9);
    opacity: 0;
  }
}

@keyframes bubble-float-3 {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  20% {
    opacity: 0.4;
  }
  80% {
    opacity: 0.4;
  }
  100% {
    transform: translateY(-220px) scale(1.2);
    opacity: 0;
  }
}

@keyframes bubble-float-4 {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  12% {
    opacity: 0.55;
  }
  88% {
    opacity: 0.55;
  }
  100% {
    transform: translateY(-260px) scale(0.95);
    opacity: 0;
  }
}

.animate-bubble-1 {
  animation: bubble-float-1 8s ease-in-out infinite;
}

.animate-bubble-2 {
  animation: bubble-float-2 10s ease-in-out infinite;
  animation-delay: 2s;
}

.animate-bubble-3 {
  animation: bubble-float-3 7s ease-in-out infinite;
  animation-delay: 4s;
}

.animate-bubble-4 {
  animation: bubble-float-4 9s ease-in-out infinite;
  animation-delay: 1s;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.bounce-enter-active {
  animation: bounce-in 0.5s;
}
.bounce-leave-active {
  animation: bounce-in 0.5s reverse;
}
@keyframes bounce-in {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.05);
    opacity: 0.5;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

.animate-shake {
  animation: shake 0.6s cubic-bezier(.36,.07,.19,.97) both;
}

/* Efecto de vidrio realista - Glassmorphism */
.glass-card {
  background: linear-gradient(135deg, rgba(254, 252, 232, 0.35), rgba(255, 251, 235, 0.3), rgba(254, 249, 195, 0.25));
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px;
  border: 1px solid rgba(180, 83, 9, 0.15);
  box-shadow: 
    0 8px 32px 0 rgba(22, 163, 74, 0.3),
    0 0 0 1px rgba(180, 83, 9, 0.1);
  padding: 1.25rem;
  position: relative;
  overflow: hidden;
}

.glass-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: -50%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(254, 240, 138, 0.2),
    transparent
  );
  transform: skewX(-25deg);
  transition: all 0.6s;
}

.glass-card:hover::before {
  left: 150%;
}

/* Efecto de vidrio azul suave para entrada - Liquid Glass */
.glass-card-blue {
  background: linear-gradient(135deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(248, 250, 255, 0.9) 25%,
    rgba(240, 245, 255, 0.85) 50%,
    rgba(248, 250, 255, 0.9) 75%,
    rgba(255, 255, 255, 0.95) 100%) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
  border-radius: 24px !important;
  border: 1px solid rgba(59, 130, 246, 0.15) !important;
  box-shadow: 
    0 8px 32px rgba(59, 130, 246, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -1px 0 rgba(59, 130, 246, 0.05) !important;
  padding: 1rem 1rem !important;
  position: relative !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}

.glass-card-blue::before {
  content: '' !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  height: 50% !important;
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.4) 0%, 
    rgba(255, 255, 255, 0) 100%) !important;
  pointer-events: none !important;
  border-radius: 24px 24px 0 0 !important;
}

/* Efecto de vidrio rojo suave para término - Liquid Glass */
.glass-card-red {
  background: linear-gradient(135deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(255, 250, 250, 0.9) 25%,
    rgba(255, 245, 245, 0.85) 50%,
    rgba(255, 250, 250, 0.9) 75%,
    rgba(255, 255, 255, 0.95) 100%) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
  border-radius: 24px !important;
  border: 1px solid rgba(239, 68, 68, 0.15) !important;
  box-shadow: 
    0 8px 32px rgba(239, 68, 68, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -1px 0 rgba(239, 68, 68, 0.05) !important;
  padding: 1rem 1rem !important;
  position: relative !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}

.glass-card-red::before {
  content: '' !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  height: 50% !important;
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.4) 0%, 
    rgba(255, 255, 255, 0) 100%) !important;
  pointer-events: none !important;
  border-radius: 24px 24px 0 0 !important;
}

/* Efecto de vidrio morado para actividades */
.glass-card-purple {
  background: linear-gradient(135deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(252, 250, 255, 0.9) 25%,
    rgba(248, 245, 255, 0.85) 50%,
    rgba(252, 250, 255, 0.9) 75%,
    rgba(255, 255, 255, 0.95) 100%) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
  border-radius: 24px !important;
  border: 1px solid rgba(168, 85, 247, 0.15) !important;
  box-shadow: 
    0 8px 32px rgba(168, 85, 247, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -1px 0 rgba(168, 85, 247, 0.05) !important;
  padding: 1rem 1rem !important;
  position: relative !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}

.glass-card-purple::before {
  content: '' !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  height: 50% !important;
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.4) 0%, 
    rgba(255, 255, 255, 0) 100%) !important;
  pointer-events: none !important;
  border-radius: 24px 24px 0 0 !important;
}

.glass-input {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  font-size: 0.875rem;
  color: #1f2937;
  transition: all 0.3s ease;
  box-shadow: 
    0 4px 16px 0 rgba(31, 38, 135, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.2);
  min-height: 36px;
  padding: 0.75rem;
}

.glass-input:focus {
  outline: none;
  border: 1px solid rgba(76, 175, 80, 0.4);
  background: rgba(255, 255, 255, 0.2);
  box-shadow: 
    0 0 0 3px rgba(76, 175, 80, 0.1),
    0 8px 25px 0 rgba(31, 38, 135, 0.15),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

.glass-input::placeholder {
  color: rgba(75, 85, 99, 0.6);
}

.glass-button {
  padding: 0.875rem 1.5rem;
  border-radius: 12px;
  border: 1px solid rgba(76, 175, 80, 0.3);
  background: linear-gradient(135deg, 
    rgba(76, 175, 80, 0.8) 0%, 
    rgba(56, 142, 60, 0.8) 100%);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  color: white;
  font-weight: 600;
  font-size: 1rem;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 4px 20px 0 rgba(76, 175, 80, 0.3),
    0 0 0 1px rgba(255, 255, 255, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.2);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.glass-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 
    0 8px 30px 0 rgba(76, 175, 80, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.2),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.3);
  background: linear-gradient(135deg, 
    rgba(76, 175, 80, 0.9) 0%, 
    rgba(56, 142, 60, 0.9) 100%);
}

.glass-button:active:not(:disabled) {
  transform: translateY(0px);
  box-shadow: 
    0 4px 15px 0 rgba(76, 175, 80, 0.3),
    inset 0 2px 4px 0 rgba(0, 0, 0, 0.1);
}

.glass-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
  transition: left 0.5s;
}

.glass-button:hover::before {
  left: 100%;
}

/* ===== BOTONES ESTILO APPLE ===== */

/* Botón secundario (Cancelar) - Estilo Apple */
.glass-button-secondary {
  padding: 0.875rem 1.5rem;
  border-radius: 14px;
  border: none;
  background: linear-gradient(180deg, 
    #f5f5f7 0%, 
    #e8e8ed 100%);
  color: #1d1d1f;
  font-weight: 600;
  font-size: 1rem;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  letter-spacing: -0.01em;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 1px 3px rgba(0, 0, 0, 0.12),
    0 1px 2px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.glass-button-secondary:hover:not(:disabled) {
  transform: scale(1.02);
  background: linear-gradient(180deg, 
    #ffffff 0%, 
    #f0f0f5 100%);
  box-shadow: 
    0 4px 12px rgba(0, 0, 0, 0.15),
    0 2px 4px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 1);
}

.glass-button-secondary:active:not(:disabled) {
  transform: scale(0.98);
  background: linear-gradient(180deg, 
    #e8e8ed 0%, 
    #d4d4d9 100%);
  box-shadow: 
    0 1px 2px rgba(0, 0, 0, 0.1),
    inset 0 2px 4px rgba(0, 0, 0, 0.05);
}

.glass-button-action {
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: linear-gradient(135deg, 
    rgba(255, 255, 255, 0.1) 0%, 
    rgba(255, 255, 255, 0.05) 100%);
}

.glass-button-action:hover:not(:disabled) {
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  box-shadow: 
    0 8px 32px 0 rgba(31, 38, 135, 0.25),
    0 0 0 1px rgba(255, 255, 255, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.3);
}

/* Botón Entrada (Azul) - Estilo Apple */
.glass-button-entrada {
  padding: 0.875rem 1.5rem;
  border-radius: 14px;
  border: none;
  background: linear-gradient(180deg, 
    #0a84ff 0%, 
    #0071e3 100%);
  color: white;
  font-weight: 600;
  font-size: 1rem;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  letter-spacing: -0.01em;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 4px 16px rgba(10, 132, 255, 0.4),
    0 2px 4px rgba(0, 112, 227, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.glass-button-entrada:hover:not(:disabled) {
  transform: scale(1.02) translateY(-1px);
  background: linear-gradient(180deg, 
    #3399ff 0%, 
    #0a84ff 100%);
  box-shadow: 
    0 8px 24px rgba(10, 132, 255, 0.5),
    0 4px 8px rgba(0, 112, 227, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.glass-button-entrada:active:not(:disabled) {
  transform: scale(0.98);
  background: linear-gradient(180deg, 
    #0071e3 0%, 
    #005bb5 100%);
  box-shadow: 
    0 2px 8px rgba(10, 132, 255, 0.3),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.glass-button-entrada::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-button-entrada:hover::before {
  left: 100%;
}

/* Estados deshabilitados estilo Apple - todos los botones */
.glass-button-entrada:disabled,
.glass-button-salida:disabled,
.glass-button-registro:disabled,
.glass-button-secondary:disabled {
  opacity: 0.5 !important;
  cursor: not-allowed !important;
  transform: none !important;
  filter: saturate(0.8);
}

.glass-button-entrada:disabled::before,
.glass-button-salida:disabled::before,
.glass-button-registro:disabled::before {
  display: none;
}

.glass-button-entrada:disabled:hover,
.glass-button-salida:disabled:hover,
.glass-button-registro:disabled:hover,
.glass-button-secondary:disabled:hover {
  transform: none !important;
  box-shadow: inherit !important;
}

/* Botón Salida (Rojo) - Estilo Apple */
.glass-button-salida {
  padding: 0.875rem 1.5rem;
  border-radius: 14px;
  border: none;
  background: linear-gradient(180deg, 
    #ff453a 0%, 
    #d70015 100%);
  color: white;
  font-weight: 600;
  font-size: 1rem;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  letter-spacing: -0.01em;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 4px 16px rgba(255, 69, 58, 0.4),
    0 2px 4px rgba(215, 0, 21, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.glass-button-salida:hover:not(:disabled) {
  transform: scale(1.02) translateY(-1px);
  background: linear-gradient(180deg, 
    #ff6961 0%, 
    #ff453a 100%);
  box-shadow: 
    0 8px 24px rgba(255, 69, 58, 0.5),
    0 4px 8px rgba(215, 0, 21, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.glass-button-salida:active:not(:disabled) {
  transform: scale(0.98);
  background: linear-gradient(180deg, 
    #d70015 0%, 
    #a50000 100%);
  box-shadow: 
    0 2px 8px rgba(255, 69, 58, 0.3),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.glass-button-salida::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-button-salida:hover::before {
  left: 100%;
}

/* Botón Registro (Morado) - Estilo Apple */
.glass-button-registro {
  padding: 0.875rem 1.5rem;
  border-radius: 14px;
  border: none;
  background: linear-gradient(180deg, 
    #bf5af2 0%, 
    #9d4edd 100%);
  color: white;
  font-weight: 600;
  font-size: 1rem;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  letter-spacing: -0.01em;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 
    0 4px 16px rgba(191, 90, 242, 0.4),
    0 2px 4px rgba(157, 78, 221, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.glass-button-registro:hover:not(:disabled) {
  transform: scale(1.02) translateY(-1px);
  background: linear-gradient(180deg, 
    #d17df5 0%, 
    #bf5af2 100%);
  box-shadow: 
    0 8px 24px rgba(191, 90, 242, 0.5),
    0 4px 8px rgba(157, 78, 221, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.glass-button-registro:active:not(:disabled) {
  transform: scale(0.98);
  background: linear-gradient(180deg, 
    #9d4edd 0%, 
    #7b2cbf 100%);
  box-shadow: 
    0 2px 8px rgba(191, 90, 242, 0.3),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.glass-button-registro::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-button-registro:hover::before {
  left: 100%;
}

.glass-link {
  position: relative;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.glass-link::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 2px;
  background: linear-gradient(90deg, #4CAF50, #81C784);
  transition: width 0.3s ease;
  border-radius: 1px;
}

.glass-link:hover::after {
  width: 100%;
}

/* Estilos para títulos de entrada y salida con franja de fondo */
.entrada-title {
  color: white;
  font-family: 'Poppins', 'DM Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  letter-spacing: -0.01em;
  font-weight: 700;
  position: relative;
  padding: 0.5rem 1rem;
  margin: -0.5rem -1rem 0.25rem -1rem;
  background: linear-gradient(
    90deg, 
    rgba(15, 55, 140, 0.9) 0%,
    rgba(15, 55, 140, 1) 50%,
    rgba(15, 55, 140, 0.9) 100%
  );
  border-left: 3px solid rgba(10, 40, 120, 1);
  border-right: 3px solid rgba(10, 40, 120, 1);
  border-radius: 0 6px 6px 0;
  box-shadow: 0 4px 16px rgba(15, 55, 140, 0.5);
}

.salida-title {
  color: white;
  font-family: 'Poppins', 'DM Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  letter-spacing: -0.01em;
  font-weight: 700;
  position: relative;
  padding: 0.5rem 1rem;
  margin: -0.5rem -1rem 0.25rem -1rem;
  background: linear-gradient(
    90deg, 
    rgba(155, 25, 45, 0.9) 0%,
    rgba(155, 25, 45, 1) 50%,
    rgba(155, 25, 45, 0.9) 100%
  );
  border-left: 3px solid rgba(120, 15, 35, 1);
  border-right: 3px solid rgba(120, 15, 35, 1);
  border-radius: 0 6px 6px 0;
  box-shadow: 0 4px 16px rgba(155, 25, 45, 0.5);
}

.purple-title {
  background: linear-gradient(
    90deg, 
    #6b21a8 0%, 
    #7c3aed 25%, 
    #c4b5fd 50%, 
    #7c3aed 75%, 
    #6b21a8 100%
  );
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gradient-wave 3s ease-in-out infinite;
  font-family: 'Poppins', 'DM Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  letter-spacing: -0.015em;
  font-weight: 700;
}

.modern-title {
  background: linear-gradient(
    90deg, 
    #166534 0%, 
    #15803d 25%, 
    #86efac 50%, 
    #15803d 75%, 
    #166534 100%
  );
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gradient-wave 3s ease-in-out infinite;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: -0.015em;
  font-weight: 500;
  position: relative;
}

.green-line {
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, #15803d, #16a34a, #15803d);
  border-radius: 0.5px;
  animation: line-glow 2s ease-in-out infinite alternate;
}

@keyframes gradient-wave {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@keyframes line-glow {
  0% {
    box-shadow: 0 0 5px rgba(34, 197, 94, 0.3);
    opacity: 0.8;
  }
  100% {
    box-shadow: 0 0 15px rgba(34, 197, 94, 0.6);
    opacity: 1;
  }
}

/* Animación para elementos decorativos */
@keyframes pulse-slow {
  0%, 100% {
    opacity: 0.3;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.05);
  }
}

.animate-pulse-slow {
  animation: pulse-slow 4s ease-in-out infinite;
}

/* Respaldo para navegadores que no soportan background-clip: text */
@supports not (-webkit-background-clip: text) {
  .modern-title {
    color: #166534;
    animation: none;
  }
}

/* Mejoras de responsividad para pantallas móviles */
@media (max-width: 480px) {
  .page-container {
    padding-left: 0.125rem;
    padding-right: 0.125rem;
    max-width: 100%;
  }
  
  .glass-card {
    padding: 0.75rem;
    margin: 0 0.125rem;
  }
  
  .glass-input {
    font-size: 14px; /* Evita zoom en iOS */
    min-height: 36px;
  }
  
  .text-xl {
    font-size: 1rem;
  }
  
  .text-lg {
    font-size: 0.875rem;
  }
  
  .text-base {
    font-size: 0.8rem;
  }
}

@media (max-height: 600px) {
  .page-container {
    max-width: 320px;
  }
  
  .glass-card {
    padding: 1rem;
  }
}

@media (max-height: 500px) {
  .glass-card {
    padding: 0.875rem;
  }
}

/* Para pantallas muy pequeñas como iPhone SE */
@media (max-width: 375px) and (max-height: 667px) {
  .page-container {
    max-width: 100%;
    padding-left: 0.125rem;
    padding-right: 0.125rem;
  }
  
  .glass-card {
    padding: 0.625rem;
    margin: 0;
  }
}

@media (max-height: 600px) {
  .page-container {
    max-width: 320px;
  }
  
  .glass-card {
    padding: 1rem;
  }
}

@media (max-height: 500px) {
  .glass-card {
    padding: 0.875rem;
  }
  
  .glass-input {
    font-size: 14px;
    min-height: 34px;
  }
}

/* Para pantallas grandes */
@media (min-width: 768px) {
  .page-container {
    max-width: 380px;
  }
  
  .glass-card {
    padding: 1.5rem;
  }
}

/* Soporte adicional para navegadores que no soportan backdrop-filter */
@supports not (backdrop-filter: blur(20px)) {
  .glass-card {
    background: rgba(255, 255, 255, 0.85);
  }
  
  .glass-input {
    background: rgba(255, 255, 255, 0.7);
  }
  
  .glass-button {
    background: linear-gradient(135deg, #4CAF50 0%, #388E3C 100%);
  }
  
  .glass-button-secondary {
    background: linear-gradient(135deg, #9CA3AF 0%, #6B7280 100%);
  }
}

/* Animación sutil para el botón de ubicación */
@keyframes pulse-subtle {
  0%, 100% {
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
    transform: translateY(0);
  }
  50% {
    box-shadow: 0 6px 20px rgba(255, 215, 0, 0.4);
    transform: translateY(-1px);
  }
}

/* Mejora de espaciado para evitar que se encimen las secciones */
.space-y-2 > * + * {
  margin-top: 0.5rem !important;
}

/* Asegurar que cada glass-card tenga su espacio definido */
.glass-card + .glass-card {
  margin-top: 0.5rem;
}

/* Espaciado específico para secciones condicionales */
.glass-card {
  margin-bottom: 0 !important; /* Remover margins bottom para usar space-y-2 */
  position: relative;
  z-index: 1;
}

/* Separación clara entre formulario de asistencia y actividades */
.page-container > .glass-card:not(:first-child) {
  clear: both;
  margin-top: 0.5rem;
}

/* Mensajes de estado sin interferir con otros elementos */
.text-center.mb-2 {
  position: relative;
  z-index: 2;
  margin-bottom: 0.5rem !important;
}

/* Estilos para botones de navegación entre secciones */
.section-nav-button {
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.section-nav-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.section-nav-button:hover::before {
  left: 100%;
}

.section-nav-button.active {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.section-nav-container {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 
    0 4px 16px 0 rgba(31, 38, 135, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
}

/* Estilos corporativos modernos para botones de ubicación */
.location-container-corporate {
  position: relative;
  margin-bottom: 1rem;
}

/* Botón principal con gradiente corporativo - Estilo Apple */
.location-button-corporate {
  background: linear-gradient(180deg, 
    #0a84ff 0%,
    #0071e3 100%
  );
  border: none;
  position: relative;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  letter-spacing: -0.01em;
  box-shadow: 
    0 4px 16px rgba(10, 132, 255, 0.4),
    0 2px 4px rgba(0, 112, 227, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.location-button-corporate:hover:not(:disabled) {
  transform: scale(1.02) translateY(-2px);
  background: linear-gradient(180deg, 
    #3399ff 0%,
    #0a84ff 100%
  );
  box-shadow: 
    0 10px 28px rgba(10, 132, 255, 0.5),
    0 4px 8px rgba(0, 112, 227, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
}

.location-button-corporate:active:not(:disabled) {
  transform: scale(0.98);
  box-shadow: 
    0 2px 8px rgba(10, 132, 255, 0.3),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Efecto de brillo superior - Apple shine effect */
.location-button-shine {
  position: absolute;
  top: 0;
  left: -150%;
  width: 150%;
  height: 100%;
  background: linear-gradient(120deg, 
    transparent 0%,
    transparent 40%, 
    rgba(255, 255, 255, 0.4) 50%,
    transparent 60%,
    transparent 100%
  );
  transition: left 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.location-button-corporate:hover .location-button-shine {
  left: 150%;
}

/* Icono wrapper con círculo de fondo */
.location-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.location-button-corporate:hover .location-icon-wrapper {
  transform: scale(1.1);
}

/* Wrapper para estado exitoso - Apple checkmark animation */
.location-icon-wrapper-success {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(48, 209, 88, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #30d158;
  animation: apple-success-bounce 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.location-icon-wrapper-success svg {
  filter: drop-shadow(0 0 8px rgba(48, 209, 88, 0.6));
}

/* Animación de aparición del icono de éxito estilo Apple */
@keyframes apple-success-bounce {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.15);
  }
  70% {
    transform: scale(0.95);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

/* Wrapper para estado deshabilitado */
.location-icon-wrapper-disabled {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
}

/* Flecha indicadora */
.location-arrow {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.location-button-corporate:hover .location-arrow {
  background: rgba(255, 255, 255, 0.2);
  transform: translateX(4px);
}

/* Botón en estado de éxito - Estilo Apple verde */
.location-button-success-corporate {
  background: linear-gradient(180deg, 
    #30d158 0%,
    #28a745 100%
  ) !important;
  border: none !important;
  box-shadow: 
    0 4px 16px rgba(48, 209, 88, 0.4),
    0 2px 4px rgba(40, 167, 69, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.location-button-success-corporate:hover:not(:disabled) {
  transform: scale(1.02) translateY(-2px) !important;
  background: linear-gradient(180deg, 
    #4ade80 0%,
    #30d158 100%
  ) !important;
  box-shadow: 
    0 10px 28px rgba(48, 209, 88, 0.5),
    0 4px 8px rgba(40, 167, 69, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.35) !important;
}

.location-button-success-corporate:active:not(:disabled) {
  transform: scale(0.98) !important;
  box-shadow: 
    0 2px 8px rgba(48, 209, 88, 0.3),
    inset 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* Botón deshabilitado - Estilo Apple */
.location-button-disabled-corporate {
  background: linear-gradient(180deg, 
    #f5f5f7 0%,
    #e8e8ed 100%
  ) !important;
  border: none !important;
  cursor: not-allowed !important;
  opacity: 0.5 !important;
  filter: saturate(0.7);
  color: #86868b !important;
}

.location-button-disabled-corporate:hover {
  transform: none !important;
  box-shadow: inherit !important;
}

/* Tarjeta de coordenadas estilo Apple */
.coordinates-card-corporate {
  margin-top: 0;
  background: linear-gradient(180deg, #30d158 0%, #28a745 100%);
  border-radius: 0 0 14px 14px;
  padding: 0.75rem 1rem;
  animation: slide-in-corporate 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-shadow: 
    0 4px 12px rgba(48, 209, 88, 0.3),
    0 2px 4px rgba(0, 0, 0, 0.08);
}

/* Badge de coordenadas - verde con blanco */
.coordinate-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  background: transparent;
  padding: 0;
  min-width: 0;
  flex-shrink: 1;
}

.coordinate-label-corp {
  font-size: 0.625rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-family: 'Inter', sans-serif;
  white-space: nowrap;
  flex-shrink: 0;
}

.coordinate-value-corp {
  font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
  font-size: 0.625rem;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

/* Animación de entrada */
@keyframes slide-in-corporate {
  0% {
    opacity: 0;
    transform: translateY(-10px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 640px) {
  .location-button-corporate {
    padding: 1rem 1.25rem;
  }
  
  .location-icon-wrapper,
  .location-icon-wrapper-success,
  .location-icon-wrapper-disabled {
    width: 44px;
    height: 44px;
  }
  
  .location-icon-wrapper-success {
    width: 52px;
    height: 52px;
  }
  
  .location-icon-wrapper svg,
  .location-icon-wrapper-disabled svg {
    width: 2rem;
    height: 2rem;
  }
  
  .location-icon-wrapper-success svg {
    width: 2.5rem !important;
    height: 2.5rem !important;
  }
  
  .coordinates-card-corporate {
    padding: 0.5rem 0.75rem;
  }
  
  .coordinate-value-corp {
    font-size: 0.5625rem;
    max-width: 80px;
  }
  
  .coordinate-label-corp {
    font-size: 0.5625rem;
  }
}

/* Nuevos estilos para botones de ubicación con diseño azul moderno */
.location-container {
  position: relative;
  margin-bottom: 1rem;
}

.location-button {
  background: linear-gradient(135deg, 
    rgba(255, 200, 0, 1) 0%,      /* Gold más intenso */
    rgba(238, 180, 34, 1) 50%,    /* Goldenrod más fuerte */
    rgba(204, 149, 11, 1) 100%    /* Gold oscuro más saturado */
  );
  border: 3px solid rgba(255, 215, 0, 1);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  box-shadow: 
    0 6px 20px 0 rgba(0, 0, 0, 0.2),
    inset 0 2px 0 0 rgba(255, 255, 255, 0.4),
    inset 0 -2px 0 0 rgba(0, 0, 0, 0.15);
  position: relative;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  font-weight: 600;
  letter-spacing: 0.025em;
  text-shadow: 0 2px 3px rgba(0, 0, 0, 0.4);
}

.location-button:hover:not(:disabled) {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 
    0 10px 25px 0 rgba(0, 0, 0, 0.3),
    inset 0 2px 0 0 rgba(255, 255, 255, 0.5),
    inset 0 -2px 0 0 rgba(0, 0, 0, 0.15);
  background: linear-gradient(135deg, 
    rgba(255, 180, 0, 1) 0%,
    rgba(255, 165, 0, 1) 50%,
    rgba(224, 140, 0, 1) 100%
  );
  border-color: rgba(255, 215, 0, 1);
}

.location-button:active:not(:disabled) {
  transform: translateY(-1px) scale(1.01);
  box-shadow: 
    0 6px 20px 0 rgba(255, 215, 0, 0.4),
    inset 0 2px 4px 0 rgba(0, 0, 0, 0.1);
}

/* Estado de éxito con efecto de vidrio (glassmorphism) y color greenyellow */
.location-button-success {
  background: rgba(154, 255, 0, 0.8) !important; /* Verde más intenso */
  backdrop-filter: blur(15px) !important;
  -webkit-backdrop-filter: blur(15px) !important;
  border: 3px solid rgba(154, 255, 0, 1) !important;
  border-top: 3px solid rgba(255, 255, 255, 0.7) !important;
  border-left: 3px solid rgba(255, 255, 255, 0.7) !important;
  box-shadow: 
    0 8px 25px 0 rgba(0, 0, 0, 0.25),
    0 0 6px 1px rgba(154, 255, 0, 0.25),
    inset 0 2px 0 0 rgba(255, 255, 255, 0.6),
    inset 0 -2px 0 0 rgba(0, 0, 0, 0.15);
  color: rgba(0, 40, 20, 0.9) !important;
  text-shadow: 0 2px 2px rgba(255, 255, 255, 0.7) !important;
  animation: glass-shine 3s ease-in-out infinite;
  position: relative;
  overflow: hidden;
}

/* Efecto de brillo para botones con efecto de vidrio */
@keyframes glass-shine {
  0% {
    background: rgba(154, 255, 0, 0.8);
    box-shadow: 
      0 8px 25px 0 rgba(0, 0, 0, 0.25),
      0 0 6px 1px rgba(154, 255, 0, 0.25);
  }
  50% {
    background: rgba(127, 255, 0, 1);
    box-shadow: 
      0 10px 30px 0 rgba(0, 0, 0, 0.3),
      0 0 10px 2px rgba(127, 255, 0, 0.35);
  }
  100% {
    background: rgba(154, 255, 0, 0.8);
    box-shadow: 
      0 8px 25px 0 rgba(0, 0, 0, 0.25),
      0 0 6px 1px rgba(154, 255, 0, 0.25);
  }
}

.location-button-success:hover:not(:disabled) {
  background: rgba(127, 255, 0, 1) !important;
  border: 3px solid rgba(127, 255, 0, 1) !important;
  border-top: 3px solid rgba(255, 255, 255, 0.8) !important;
  border-left: 3px solid rgba(255, 255, 255, 0.8) !important;
  box-shadow: 
    0 10px 30px 0 rgba(0, 0, 0, 0.3),
    inset 0 2px 0 0 rgba(255, 255, 255, 0.7);
  transform: translateY(-3px) scale(1.03);
}

/* Efecto de reflejos para el botón de ubicación obtenida */
.location-button-success::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(
    to right,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.1) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  transform: rotate(30deg);
  animation: glass-sweep 6s infinite linear;
}

@keyframes glass-sweep {
  0% {
    transform: rotate(30deg) translateX(-100%);
  }
  50% {
    transform: rotate(30deg) translateX(100%);
  }
  100% {
    transform: rotate(30deg) translateX(100%);
  }
}

/* Efecto de brillo para el botón normal */
.location-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.6s;
}

.location-button:hover::before {
  left: 100%;
}

/* Contenedor y estilos para las coordenadas */
.coordinates-display {
  margin-top: 0.5rem;
  background: linear-gradient(135deg, 
    rgba(255, 215, 0, 0.08) 0%,
    rgba(218, 165, 32, 0.12) 100%
  );
  border: 1px solid rgba(255, 215, 0, 0.2);
  border-radius: 8px;
  padding: 0.5rem;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 
    0 2px 8px 0 rgba(255, 215, 0, 0.1),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
  animation: slide-down 0.3s ease-out;
}

.coordinates-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.coordinate-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.coordinate-label {
  font-size: 0.5rem;
  font-weight: 600;
  color: rgba(255, 215, 0, 0.8);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.125rem;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.coordinate-value {
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
  font-size: 0.6rem;
  font-weight: 600;
  color: rgba(218, 165, 32, 0.9);
  background: rgba(255, 255, 255, 0.6);
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  border: 1px solid rgba(255, 215, 0, 0.15);
  word-break: break-all;
  line-height: 1.1;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

/* Estilos para los elementos dentro del botón de vidrio */
.glass-text {
  color: rgba(0, 40, 20, 0.9);
  text-shadow: 0 1px 1px rgba(255, 255, 255, 0.5);
  letter-spacing: 0.05em;
  font-weight: 600;
}

.glass-icon {
  filter: drop-shadow(0 1px 1px rgba(255, 255, 255, 0.5));
  color: rgba(0, 40, 20, 0.7) !important;
  opacity: 0.9;
}

.text-dark-green {
  color: rgba(0, 40, 20, 0.8);
}

/* Efectos para el botón Obtener Ubicación */
.location-text {
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
}

.location-icon {
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
  transition: all 0.3s ease;
}

.location-button:hover .location-text {
  letter-spacing: 0.05em;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.location-button:hover .location-icon {
  transform: scale(1.1);
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.4));
}

/* Animaciones */
@keyframes success-pulse {
  0%, 100% {
    box-shadow: 
      0 8px 32px 0 rgba(63, 222, 153, 0.4),
      0 0 0 1px rgba(255, 255, 255, 0.2),
      inset 0 1px 0 0 rgba(255, 255, 255, 0.4);
  }
  50% {
    box-shadow: 
      0 8px 32px 0 rgba(63, 222, 153, 0.6),
      0 0 0 2px rgba(63, 222, 153, 0.3),
      inset 0 1px 0 0 rgba(255, 255, 255, 0.5);
  }
}

@keyframes slide-down {
  0% {
    opacity: 0;
    transform: translateY(-10px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive para coordenadas */
@media (max-width: 480px) {
  .coordinates-display {
    padding: 0.375rem;
  }
  
  .coordinate-label {
    font-size: 0.45rem;
  }
  
  .coordinate-value {
    font-size: 0.55rem;
    padding: 0.1rem 0.2rem;
  }
  
  .coordinates-grid {
    gap: 0.375rem;
  }
  
  .location-button {
    padding: 0.75rem 1rem;
  }
}

/* Animaciones para el efecto vidrio líquido */
@keyframes float {
  0%, 100% {
    transform: translateY(0px) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translateY(-4px) scale(1.1);
    opacity: 0.8;
  }
}

@keyframes shimmer {
  0% {
    transform: skew(6deg) translateX(-200%);
  }
  100% {
    transform: skew(6deg) translateX(200%);
  }
}

@keyframes liquid-float {
  0%, 100% {
    transform: translateY(0px) rotate(0deg);
  }
  33% {
    transform: translateY(-2px) rotate(1deg);
  }
  66% {
    transform: translateY(1px) rotate(-1deg);
  }
}

/* Clases para las animaciones */
.animate-float {
  animation: float 3s ease-in-out infinite;
}

.animate-shimmer {
  animation: shimmer 3s ease-in-out infinite;
}

.animate-liquid-float {
  animation: liquid-float 4s ease-in-out infinite;
}

/* Efectos adicionales para el vidrio líquido */
.glass-liquid {
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.2),
    rgba(255, 255, 255, 0.1)
  );
}

.liquid-glow {
  box-shadow: 
    0 4px 20px rgba(244, 63, 94, 0.15),
    0 0 40px rgba(244, 63, 94, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.soft-pulse {
  animation: soft-pulse 4s ease-in-out infinite;
}

@keyframes soft-pulse {
  0%, 100% {
    opacity: 0.6;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.05);
  }
}

/* Animación elegante para el mensaje de estado */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-5px) scale(0.98);
}

.fade-slide-enter-to,
.fade-slide-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Estilos responsivos mejorados para botones de asistencia */
@media (min-width: 768px) {
  .grid.md\\:grid-cols-2 {
    align-items: stretch;
  }
  
  .grid.md\\:grid-cols-2 button {
    min-height: 140px;
  }
}

@media (max-width: 767px) {
  .grid button {
    min-height: 120px;
  }
}

/* Asegurar que los botones tengan diseño consistente */
.grid button {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  box-sizing: border-box;
}

/* Mejorar transiciones y hover effects */
.grid button:not(:disabled):hover {
  transform: scale(1.02);
}

.grid button:not(:disabled):active {
  transform: scale(0.98);
}

/* Animación de brillo para el título Panel de Registro */
.title-shine {
  position: relative;
}

.title-shine span {
  display: inline-block;
  animation: letter-shine 4s ease-in-out infinite;
  animation-delay: calc(var(--char-index) * 0.1s);
}

.title-shine .space-char {
  min-width: 0.5em;
  display: inline-block;
}

@keyframes letter-shine {
  0%, 70% {
    text-shadow: none;
    filter: brightness(1);
    transform: scale(1);
  }
  75% {
    text-shadow: 
      0 0 8px rgba(234, 179, 8, 0.8),
      0 0 15px rgba(234, 179, 8, 0.6),
      0 0 20px rgba(234, 179, 8, 0.4);
    filter: brightness(1.5);
    transform: scale(1.1);
  }
  80% {
    text-shadow: none;
    filter: brightness(1);
    transform: scale(1);
  }
  100% {
    text-shadow: none;
    filter: brightness(1);
    transform: scale(1);
  }
}

/* Línea amarilla para Panel de Registro */
.yellow-line {
  width: 180px;
  height: 2px;
  background: linear-gradient(90deg, #eab308, #f59e0b, #eab308);
  border-radius: 1px;
  box-shadow: 0 1px 3px rgba(234, 179, 8, 0.3);
}

/* Botones de foto con efecto liquid glass */
.photo-button-glass {
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  -webkit-tap-highlight-color: transparent;
  font-size: 0.95rem;
  letter-spacing: 0.3px;
}

.photo-button-glass::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  transition: left 0.5s ease;
}

.photo-button-glass:hover::before {
  left: 100%;
}

/* Botón de cámara - rosa fuerte liquid glass */
.photo-button-pink {
  background: linear-gradient(
    135deg,
    rgba(236, 72, 153, 0.65) 0%,
    rgba(219, 39, 119, 0.7) 50%,
    rgba(190, 24, 93, 0.75) 100%
  );
}

.photo-button-pink:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(236, 72, 153, 0.75) 0%,
    rgba(219, 39, 119, 0.8) 50%,
    rgba(190, 24, 93, 0.85) 100%
  );
  transform: translateY(-2px);
}

.photo-button-pink:active:not(:disabled) {
  transform: translateY(0);
}

/* Botón de galería - gris liquid glass */
.photo-button-gallery {
  background: linear-gradient(
    135deg,
    rgba(75, 85, 99, 0.65) 0%,
    rgba(55, 65, 81, 0.7) 50%,
    rgba(31, 41, 55, 0.75) 100%
  );
}

.photo-button-gallery:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(75, 85, 99, 0.75) 0%,
    rgba(55, 65, 81, 0.8) 50%,
    rgba(31, 41, 55, 0.85) 100%
  );
  transform: translateY(-2px);
}

.photo-button-gallery:active:not(:disabled) {
  transform: translateY(0);
}

/* Efecto disabled para botones de foto */
.photo-button-glass:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.photo-button-glass:disabled::before {
  display: none;
}

/* ===== ESTILOS APPLE PARA REGISTRO DE ASISTENCIA ===== */

/* Estilos globales para evitar desbordamiento */
[class*="apple-"] {
  box-sizing: border-box;
  max-width: 100%;
}

.apple-form-container *,
.apple-attendance-container *,
.apple-activities-container * {
  box-sizing: border-box;
}

/* Asegurar que todos los elementos respeten el ancho del contenedor */
.apple-header-card,
.apple-user-card,
.apple-step-card,
.apple-step-card-purple,
.apple-checklist-card,
.apple-ready-card,
.apple-warning-card,
.apple-action-buttons,
.apple-photo-buttons,
.apple-textarea,
.apple-select,
.apple-input {
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

/* Contenedor principal del formulario */
.apple-form-container,
.apple-attendance-container {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  animation: apple-fade-in 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Espaciado lateral para elementos hijos de asistencias */
.apple-attendance-container > .apple-header-card,
.apple-attendance-container > .apple-user-card,
.apple-attendance-container > .apple-step-card,
.apple-attendance-container > .apple-action-buttons,
.apple-attendance-container > .apple-checklist-card,
.apple-attendance-container > .apple-ready-card {
  margin-left: 0;
  margin-right: 0;
  max-width: 100%;
  box-sizing: border-box;
}

@keyframes apple-fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Header card - estilo Apple */
.apple-header-card {
  padding: 0.625rem 0.875rem !important;
  border-radius: 16px;
  position: relative;
  overflow: hidden;
}

.apple-header-entrada {
  background: linear-gradient(135deg, #0a84ff 0%, #0066cc 100%);
  box-shadow: 
    0 8px 24px rgba(10, 132, 255, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-header-salida {
  background: linear-gradient(135deg, #ff453a 0%, #cc3333 100%);
  box-shadow: 
    0 8px 24px rgba(255, 69, 58, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-header-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.apple-header-icon svg {
  width: 18px;
  height: 18px;
}

.apple-header-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
  font-size: 0.9375rem;
  font-weight: 600;
  color: white;
  letter-spacing: -0.02em;
  margin: 0;
  white-space: nowrap;
}

/* User card estilo Apple */
.apple-user-card {
  background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  padding: 0.625rem 0.875rem !important;
  box-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.04),
    0 1px 2px rgba(0, 0, 0, 0.02);
}

.apple-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
}

.apple-avatar-blue {
  background: linear-gradient(180deg, #e1f0ff 0%, #cce4ff 100%);
  border: 2px solid #0a84ff;
}

.apple-avatar-red {
  background: linear-gradient(180deg, #ffe5e5 0%, #ffcccc 100%);
  border: 2px solid #ff453a;
}

.apple-avatar-initials {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1d1d1f;
}

.apple-user-name {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.01em;
}

.apple-user-role {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.75rem;
  color: #86868b;
}

.apple-status-badge {
  padding: 0.25rem 0.625rem;
  border-radius: 100px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.apple-badge-blue {
  background: rgba(10, 132, 255, 0.1);
  color: #0a84ff;
}

.apple-badge-red {
  background: rgba(255, 69, 58, 0.1);
  color: #ff453a;
}

/* Step cards estilo Apple */
.apple-step-card {
  background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  padding: 0.5rem 0.875rem !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.apple-step-card:hover {
  border-color: rgba(0, 0, 0, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.apple-step-number {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: linear-gradient(180deg, #0a84ff 0%, #0071e3 100%);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.6875rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.5rem;
  box-shadow: 0 2px 6px rgba(10, 132, 255, 0.3);
  flex-shrink: 0;
}

.apple-step-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.01em;
}

.apple-completed-badge {
  display: flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 100px;
  background: rgba(48, 209, 88, 0.1);
  color: #30d158;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  font-weight: 500;
  animation: apple-badge-pop 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes apple-badge-pop {
  0% { transform: scale(0.8); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

/* Image preview estilo Apple */
.apple-image-preview {
  position: relative;
  width: 100%;
  height: 140px;
  border-radius: 12px;
  overflow: hidden;
  background: #f5f5f7;
  box-shadow: 
    0 4px 12px rgba(0, 0, 0, 0.1),
    inset 0 0 0 1px rgba(0, 0, 0, 0.05);
}

.apple-image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.75rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
  display: flex;
  justify-content: flex-end;
}

.apple-delete-image-btn {
  display: flex;
  align-items: center;
  padding: 0.375rem 0.75rem;
  border-radius: 100px;
  background: rgba(255, 69, 58, 0.9);
  backdrop-filter: blur(10px);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.apple-delete-image-btn:hover {
  background: rgba(255, 69, 58, 1);
  transform: scale(1.05);
}

.apple-delete-image-btn:active {
  transform: scale(0.95);
}

/* Photo buttons estilo Apple */
.apple-photo-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.apple-photo-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0.75rem 0.5rem;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  min-height: 70px;
}

.apple-photo-btn-camera {
  background: linear-gradient(180deg, #d6214c 0%, #a81839 100%);
  color: white;
  box-shadow: 
    0 4px 14px rgba(214, 33, 76, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.apple-photo-btn-gallery {
  background: linear-gradient(180deg, #4442a8 0%, #362f8c 100%);
  color: white;
  box-shadow: 
    0 4px 14px rgba(68, 66, 168, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.apple-photo-btn:hover {
  transform: scale(1.02) translateY(-2px);
  box-shadow: 
    0 8px 20px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-photo-btn:active {
  transform: scale(0.98);
}

.apple-photo-btn-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
}

.apple-photo-btn-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.apple-photo-btn-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.apple-photo-btn-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.apple-photo-btn-subtitle {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  opacity: 0.85;
}

/* Textarea estilo Apple */
.apple-textarea {
  width: 100%;
  padding: 0.875rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.875rem;
  color: #1d1d1f;
  resize: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04);
}

.apple-textarea:focus {
  outline: none;
  border-color: #0a84ff;
  box-shadow: 
    0 0 0 3px rgba(10, 132, 255, 0.15),
    inset 0 1px 2px rgba(0, 0, 0, 0.02);
}

.apple-textarea::placeholder {
  color: #86868b;
}

/* Action buttons estilo Apple */
.apple-action-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.apple-btn-cancel {
  flex: 0.4;
  padding: 0.875rem 1rem;
  border-radius: 12px;
  border: none;
  background: linear-gradient(180deg, #f5f5f7 0%, #e8e8ed 100%);
  color: #1d1d1f;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 
    0 2px 6px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.apple-btn-cancel:hover {
  background: linear-gradient(180deg, #ffffff 0%, #f0f0f5 100%);
  transform: scale(1.02);
}

.apple-btn-cancel:active {
  transform: scale(0.98);
  background: linear-gradient(180deg, #e8e8ed 0%, #d8d8de 100%);
}

.apple-btn-submit {
  flex: 0.6;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.875rem 1.25rem;
  border-radius: 12px;
  border: none;
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  position: relative;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.apple-btn-entrada {
  background: linear-gradient(180deg, #0a84ff 0%, #0071e3 100%);
  box-shadow: 
    0 4px 14px rgba(10, 132, 255, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-btn-salida {
  background: linear-gradient(180deg, #ff453a 0%, #d70015 100%);
  box-shadow: 
    0 4px 14px rgba(255, 69, 58, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-btn-submit:hover:not(.apple-btn-disabled) {
  transform: scale(1.02) translateY(-1px);
}

.apple-btn-submit:active:not(.apple-btn-disabled) {
  transform: scale(0.98);
}

.apple-btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  filter: saturate(0.8);
}

/* Spinner estilo Apple */
.apple-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.apple-spinner-ring {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: apple-spin 0.8s linear infinite;
}

@keyframes apple-spin {
  to { transform: rotate(360deg); }
}

/* Checklist card estilo Apple - Amarillo oscuro */
.apple-checklist-card {
  background: linear-gradient(135deg, #fef9e7 0%, #fcf3cf 100%);
  border: 1px solid rgba(180, 140, 0, 0.2);
  border-radius: 14px;
  padding: 0.75rem 0.875rem !important;
  box-shadow: 0 2px 8px rgba(180, 140, 0, 0.1);
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.apple-checklist-header {
  display: flex;
  align-items: center;
  margin-bottom: 0.75rem;
}

.apple-checklist-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(180deg, #d4a000 0%, #b8860b 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 0.625rem;
  box-shadow: 0 2px 6px rgba(180, 134, 11, 0.35);
}

.apple-checklist-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.01em;
}

.apple-checklist-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  max-width: 100%;
}

.apple-checklist-item {
  flex: 1 1 calc(50% - 0.25rem);
  min-width: 100px;
  max-width: calc(50% - 0.25rem);
  display: flex;
  align-items: center;
  padding: 0.5rem 0.625rem;
  border-radius: 10px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  overflow: hidden;
  white-space: nowrap;
}

/* Estados del item del checklist */
.apple-checklist-done,
.apple-checklist-item-done {
  background: rgba(48, 209, 88, 0.1);
  color: #30d158;
  border: 1px solid rgba(48, 209, 88, 0.2);
}

.apple-checklist-pending,
.apple-checklist-item-pending {
  background: rgba(142, 142, 147, 0.1);
  color: #8e8e93;
  border: 1px solid rgba(142, 142, 147, 0.15);
}

/* Círculo de check */
.apple-checklist-check,
.apple-checklist-circle {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.375rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}

.apple-check-done,
.apple-checklist-circle-done {
  background: linear-gradient(180deg, #30d158 0%, #28a745 100%);
  box-shadow: 0 2px 4px rgba(48, 209, 88, 0.3);
}

.apple-check-pending,
.apple-checklist-circle-pending {
  background: #c7c7cc;
}

/* Ready card estilo Apple */
.apple-ready-card {
  background: linear-gradient(135deg, rgba(48, 209, 88, 0.1) 0%, rgba(52, 199, 89, 0.15) 100%);
  border: 1px solid rgba(48, 209, 88, 0.25);
  border-radius: 14px;
  padding: 0.75rem 0.5rem;
  animation: apple-ready-pop 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes apple-ready-pop {
  0% {
    transform: scale(0.95);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.apple-ready-content {
  display: flex;
  align-items: center;
  justify-content: center;
}

.apple-ready-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(180deg, #30d158 0%, #28a745 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.5rem;
  animation: apple-pulse-icon 1.5s ease-in-out infinite;
  box-shadow: 0 3px 8px rgba(48, 209, 88, 0.4);
}

@keyframes apple-pulse-icon {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.apple-ready-text {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #30d158;
  letter-spacing: -0.01em;
}

/* ========================================
   ESTILOS APPLE PARA SECCIÓN ACTIVIDADES (MORADO)
   ======================================== */

/* Contenedor principal actividades - Liquid Glass */
.apple-activities-container {
  background: linear-gradient(135deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(252, 250, 255, 0.9) 25%,
    rgba(248, 245, 255, 0.85) 50%,
    rgba(252, 250, 255, 0.9) 75%,
    rgba(255, 255, 255, 0.95) 100%) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
  border: 1px solid rgba(147, 51, 234, 0.15);
  border-radius: 24px;
  padding: 1rem 1rem !important;
  box-shadow: 
    0 8px 32px rgba(147, 51, 234, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    inset 0 -1px 0 rgba(147, 51, 234, 0.05);
  animation: apple-fade-in 0.4s ease-out;
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

/* Espaciado lateral para elementos hijos */
.apple-activities-container > .apple-warning-card,
.apple-activities-container > .apple-header-card,
.apple-activities-container > .apple-user-card,
.apple-activities-container > form {
  margin-left: 0;
  margin-right: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.apple-activities-container > form > .apple-step-card-purple,
.apple-activities-container > form > .apple-checklist-card,
.apple-activities-container > form > .apple-ready-card,
.apple-activities-container > form > button {
  margin-left: 0;
  margin-right: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.apple-activities-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.4) 0%, 
    rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
  border-radius: 24px 24px 0 0;
}

/* Header morado */
.apple-header-purple {
  background: linear-gradient(180deg, #9333ea 0%, #7c3aed 100%);
  box-shadow: 
    0 4px 14px rgba(147, 51, 234, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

/* Avatar morado */
.apple-avatar-purple {
  background: linear-gradient(180deg, rgba(147, 51, 234, 0.1) 0%, rgba(124, 58, 237, 0.15) 100%);
  border-color: #9333ea;
}

.apple-avatar-purple .apple-avatar-initials {
  color: #7c3aed;
}

/* Badge morado */
.apple-badge-purple {
  background: rgba(147, 51, 234, 0.1);
  color: #9333ea;
}

/* Step card morado */
.apple-step-card-purple {
  background: linear-gradient(180deg, #ffffff 0%, #fdfaff 100%);
  border: 1px solid rgba(147, 51, 234, 0.1);
  border-radius: 12px;
  padding: 0.5rem 0.875rem !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.apple-step-card-purple:hover {
  border-color: rgba(147, 51, 234, 0.2);
  box-shadow: 0 4px 12px rgba(147, 51, 234, 0.08);
}

/* Step number morado */
.apple-step-number-purple {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: linear-gradient(180deg, #9333ea 0%, #7c3aed 100%);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.6875rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.5rem;
  box-shadow: 0 2px 6px rgba(147, 51, 234, 0.3);
  flex-shrink: 0;
}

/* Warning card estilo Apple */
.apple-warning-card {
  background: linear-gradient(135deg, rgba(255, 214, 10, 0.15) 0%, rgba(255, 149, 0, 0.1) 100%);
  border: 1px solid rgba(255, 149, 0, 0.3);
  border-left: 4px solid #ff9500;
  border-radius: 12px;
  padding: 0.75rem 0.5rem;
  animation: apple-fade-in 0.3s ease-out;
}

.apple-warning-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 149, 0, 0.15);
  color: #ff9500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.apple-warning-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #995a00;
  letter-spacing: -0.01em;
}

.apple-warning-text {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.75rem;
  color: #996600;
  margin-top: 0.25rem;
}

/* Select estilo Apple */
.apple-select {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.875rem;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(147, 51, 234, 0.15);
  background: linear-gradient(180deg, #ffffff 0%, #fdfaff 100%);
  color: #1d1d1f;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.apple-select:focus {
  border-color: #9333ea;
  box-shadow: 0 0 0 3px rgba(147, 51, 234, 0.15);
}

/* Input estilo Apple */
.apple-input {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.875rem;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  color: #1d1d1f;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.apple-input:focus {
  border-color: #9333ea;
  box-shadow: 0 0 0 3px rgba(147, 51, 234, 0.15);
  background: #ffffff;
}

.apple-input-label {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  color: #86868b;
}

/* Textarea estilo Apple */
.apple-textarea {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.875rem;
  padding: 0.875rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(147, 51, 234, 0.12);
  background: linear-gradient(180deg, #ffffff 0%, #fdfaff 100%);
  color: #1d1d1f;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  resize: vertical;
  min-height: 80px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.apple-textarea:focus {
  border-color: #9333ea;
  box-shadow: 0 0 0 3px rgba(147, 51, 234, 0.15);
  background: #ffffff;
}

.apple-textarea::placeholder {
  color: #86868b;
  font-weight: 400;
}

/* Botones de foto oscuros para actividades */
.apple-photo-btn-camera-dark {
  background: linear-gradient(180deg, #d6214c 0%, #a81839 100%);
  color: white;
  box-shadow: 
    0 4px 14px rgba(214, 33, 76, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.apple-photo-btn-gallery-dark {
  background: linear-gradient(180deg, #4442a8 0%, #362f8c 100%);
  color: white;
  box-shadow: 
    0 4px 14px rgba(68, 66, 168, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.apple-photo-btn-text {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-top: 0.5rem;
}

/* Vista previa de foto estilo Apple */
.apple-photo-preview {
  position: relative;
  animation: apple-fade-in 0.3s ease-out;
}

.apple-photo-container {
  width: 100%;
  height: 140px;
  border-radius: 14px;
  overflow: hidden;
  background: #f5f5f7;
  border: 1px solid rgba(147, 51, 234, 0.15);
  box-shadow: 
    0 4px 12px rgba(147, 51, 234, 0.1),
    inset 0 0 0 1px rgba(0, 0, 0, 0.05);
}

.apple-photo-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0.75rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.5));
  display: flex;
  justify-content: flex-end;
  border-radius: 0 0 14px 14px;
}

.apple-photo-delete-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 100px;
  background: rgba(255, 69, 58, 0.9);
  backdrop-filter: blur(10px);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.apple-photo-delete-btn:hover {
  background: rgba(255, 69, 58, 1);
  transform: scale(1.05);
}

.apple-photo-delete-btn:active {
  transform: scale(0.95);
}

/* ========================================
   MEDIA QUERIES RESPONSIVAS ESTILO APPLE
   ======================================== */

/* Pantallas pequeñas (móviles) */
@media (max-width: 374px) {
  .apple-header-card {
    padding: 0.5rem 0.75rem !important;
    border-radius: 12px;
  }
  
  .apple-header-icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    margin-right: 0.5rem;
  }
  
  .apple-header-icon svg {
    width: 16px;
    height: 16px;
  }
  
  .apple-header-title {
    font-size: 0.8125rem;
  }
  
  .apple-step-card,
  .apple-step-card-purple {
    padding: 0.5rem 0.75rem !important;
    border-radius: 12px;
  }

  .apple-step-number,
  .apple-step-number-purple {
    width: 18px;
    height: 18px;
    font-size: 0.625rem;
    margin-right: 0.375rem;
  }

  .apple-step-title {
    font-size: 0.75rem;
  }

  .apple-user-card {
    padding: 0.5rem 0.75rem !important;
    border-radius: 12px;
  }
  
  .apple-avatar,
  .apple-avatar-purple {
    width: 36px;
    height: 36px;
  }
  
  .apple-avatar-initials {
    font-size: 0.6875rem;
  }
  
  .apple-photo-buttons {
    gap: 0.375rem;
  }
  
  .apple-photo-btn {
    padding: 0.625rem 0.375rem;
    min-height: 60px;
  }
  
  .apple-checklist-card {
    padding: 0.5rem 0.5rem !important;
  }
  
  .apple-checklist-items {
    gap: 0.375rem;
  }
  
  .apple-checklist-item {
    flex: 1 1 calc(50% - 0.1875rem);
    max-width: calc(50% - 0.1875rem);
    min-width: 90px;
    padding: 0.375rem 0.5rem;
    font-size: 0.625rem;
  }
  
  .apple-checklist-item span {
    font-size: 0.625rem;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .apple-checklist-title {
    font-size: 0.75rem;
  }
  
  .glass-card-blue,
  .glass-card-red {
    padding: 1rem 0.75rem !important;
  }
  
  .apple-activities-container {
    padding: 1rem 0.75rem !important;
  }
}

/* Pantallas medianas (móviles grandes) */
@media (min-width: 375px) and (max-width: 428px) {
  .apple-header-card {
    padding: 0.5rem 0.875rem !important;
  }
  
  .apple-header-icon {
    width: 30px;
    height: 30px;
  }
  
  .apple-header-icon svg {
    width: 17px;
    height: 17px;
  }
  
  .apple-header-title {
    font-size: 0.875rem;
  }
  
  .apple-step-number,
  .apple-step-number-purple {
    width: 19px;
    height: 19px;
  }
  
  .apple-step-title {
    font-size: 0.8125rem;
  }
  
  .apple-checklist-item {
    flex: 1 1 calc(50% - 0.25rem);
    max-width: calc(50% - 0.25rem);
    min-width: 95px;
    padding: 0.4375rem 0.5625rem;
  }
  
  .glass-card-blue,
  .glass-card-red {
    padding: 1rem 0.875rem !important;
  }
  
  .apple-activities-container {
    padding: 1rem 0.875rem !important;
  }
}

/* Pantallas grandes (tablets y desktop) */
@media (min-width: 429px) {
  .apple-header-card {
    padding: 0.625rem 1rem !important;
  }
  
  .apple-header-icon {
    width: 34px;
    height: 34px;
    border-radius: 10px;
  }
  
  .apple-header-icon svg {
    width: 20px;
    height: 20px;
  }
  
  .apple-header-title {
    font-size: 1rem;
  }
  
  .apple-step-number,
  .apple-step-number-purple {
    width: 22px;
    height: 22px;
    font-size: 0.75rem;
  }
  
  .apple-step-title {
    font-size: 0.875rem;
  }
  
  .apple-checklist-item {
    flex: 1 1 calc(50% - 0.25rem);
    max-width: calc(50% - 0.25rem);
    min-width: 100px;
  }
  
  .glass-card-blue,
  .glass-card-red,
  .apple-activities-container {
    padding: 1rem 1rem !important;
  }
  
  .apple-step-card,
  .apple-step-card-purple {
    padding: 0.5rem 1rem !important;
  }
}

/* Tablets */
@media (min-width: 768px) {
  .apple-activities-container,
  .apple-attendance-container {
    max-width: 500px;
    margin: 0 auto;
  }
  
  .apple-header-title {
    font-size: 1.0625rem;
  }
}

/* ========================================
   BOTÓN DE UBICACIÓN APPLE CIRCULAR
   ======================================== */

.apple-location-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.875rem;
  padding: 0.5rem 0;
}

.apple-location-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.625rem;
}

/* Botón circular principal */
.apple-location-btn {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  -webkit-tap-highlight-color: transparent;
}

/* Estado default - azul Apple */
.apple-location-btn-default {
  background: linear-gradient(180deg, #0a84ff 0%, #0071e3 100%);
  box-shadow: 
    0 6px 20px rgba(10, 132, 255, 0.4),
    0 2px 6px rgba(10, 132, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-location-btn-default:hover {
  transform: scale(1.05);
  box-shadow: 
    0 8px 28px rgba(10, 132, 255, 0.5),
    0 4px 10px rgba(10, 132, 255, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.apple-location-btn-default:active {
  transform: scale(0.95);
  box-shadow: 
    0 3px 12px rgba(10, 132, 255, 0.4),
    inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Estado loading */
.apple-location-btn-loading {
  background: linear-gradient(180deg, #5ac8fa 0%, #34aadc 100%);
  box-shadow: 
    0 6px 20px rgba(90, 200, 250, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  cursor: wait;
}

/* Estado success - verde Apple */
.apple-location-btn-success {
  background: linear-gradient(180deg, #30d158 0%, #28a745 100%);
  box-shadow: 
    0 6px 20px rgba(48, 209, 88, 0.4),
    0 2px 6px rgba(48, 209, 88, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.apple-location-btn-success:hover {
  transform: scale(1.02);
}

/* Estado disabled - gris Apple */
.apple-location-btn-disabled {
  background: linear-gradient(180deg, #8e8e93 0%, #636366 100%);
  box-shadow: 
    0 4px 12px rgba(142, 142, 147, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  cursor: not-allowed;
  opacity: 0.7;
}

/* Icono central */
.apple-location-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  z-index: 2;
}

/* Anillo de progreso animado estilo Apple */
.apple-location-ring {
  position: absolute;
  inset: -6px;
  z-index: 1;
  animation: apple-ring-rotate 1s linear infinite;
}

.apple-location-ring-svg {
  width: 100%;
  height: 100%;
}

.apple-location-ring-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.15);
  stroke-width: 4;
}

.apple-location-ring-progress {
  fill: none;
  stroke: white;
  stroke-width: 4;
  stroke-linecap: round;
  /* Circunferencia = 2 * PI * r = 2 * 3.14159 * 45 = 282.74 */
  /* Mostrar ~25% del arco visible */
  stroke-dasharray: 70 213;
  stroke-dashoffset: 0;
  transform-origin: center;
}

@keyframes apple-ring-rotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* Pulso de éxito */
.apple-location-pulse {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(48, 209, 88, 0.3);
  animation: apple-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  z-index: 0;
}

@keyframes apple-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.15);
    opacity: 0;
  }
}

/* Información de ubicación */
.apple-location-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
}

.apple-location-title {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.01em;
}

.apple-location-subtitle {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.6875rem;
  font-weight: 400;
  color: #86868b;
}

/* Coordenadas compactas */
.apple-coordinates {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(48, 209, 88, 0.08) 0%, rgba(52, 199, 89, 0.12) 100%);
  border: 1px solid rgba(48, 209, 88, 0.2);
  border-radius: 100px;
  padding: 0.25rem 0.5rem;
  animation: apple-coords-appear 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  max-width: 100%;
  overflow: hidden;
}

@keyframes apple-coords-appear {
  from {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.apple-coord-item {
  display: flex;
  align-items: center;
  gap: 0.125rem;
  min-width: 0;
  flex-shrink: 1;
}

.apple-coord-label {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  font-size: 0.5rem;
  font-weight: 600;
  color: #30d158;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.apple-coord-value {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', 'Menlo', monospace;
  font-size: 0.5625rem;
  font-weight: 500;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}

.apple-coord-divider {
  width: 1px;
  height: 10px;
  background: rgba(48, 209, 88, 0.3);
  margin: 0 0.375rem;
  flex-shrink: 0;
}

/* Responsividad del botón de ubicación */
@media (max-width: 374px) {
  .apple-location-btn {
    width: 64px;
    height: 64px;
  }
  
  .apple-location-icon svg {
    width: 24px;
    height: 24px;
  }
  
  .apple-location-title {
    font-size: 0.75rem;
  }
  
  .apple-location-subtitle {
    font-size: 0.625rem;
  }
  
  .apple-coordinates {
    padding: 0.1875rem 0.375rem;
  }
  
  .apple-coord-label {
    font-size: 0.4375rem;
  }
  
  .apple-coord-value {
    font-size: 0.5rem;
    max-width: 60px;
  }
  
  .apple-coord-divider {
    margin: 0 0.25rem;
    height: 8px;
  }
}

@media (min-width: 375px) and (max-width: 428px) {
  .apple-coord-value {
    max-width: 70px;
  }
}

@media (min-width: 429px) {
  .apple-location-btn {
    width: 80px;
    height: 80px;
  }
  
  .apple-location-icon svg {
    width: 32px;
    height: 32px;
  }
  
  .apple-location-title {
    font-size: 0.875rem;
  }
  
  .apple-location-subtitle {
    font-size: 0.75rem;
  }
  
  .apple-coord-value {
    max-width: 100px;
    font-size: 0.625rem;
  }
  
  .apple-coord-label {
    font-size: 0.5625rem;
  }
}

/* =====================================================================
   NUEVO DISEÑO DEL HOME  (prefijo hm-)
   Principios: ligero (sin blur ni blobs animados), táctil, legible al
   sol, estados claros (disponible / completado / bloqueado) y adaptable
   desde 320px hasta tablets.
   ===================================================================== */

.hm-root {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: linear-gradient(160deg, #f0fdf4 0%, #dcfce7 55%, #c8f5dc 100%);
  --hm-radius: 22px;
  --hm-ink: #0f2a1a;
  --hm-muted: #5b6b62;
  --hm-blue-a: #3aa4ff;
  --hm-blue-b: #0a67ee;
  --hm-red-a: #ff5c7c;
  --hm-red-b: #d31b48;
}

/* Una sola capa decorativa estática (sin blur, sin animación) */
.hm-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  contain: strict;
  background:
    radial-gradient(55% 32% at 12% 4%, rgba(74, 222, 128, 0.32), transparent 70%),
    radial-gradient(50% 34% at 96% 26%, rgba(45, 212, 191, 0.24), transparent 70%),
    radial-gradient(65% 40% at 30% 100%, rgba(16, 185, 129, 0.22), transparent 70%);
}

/* Área con scroll propio: deja espacio al header fijo (barra + franja de conexión) */
.hm-scroll {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding:
    calc(env(safe-area-inset-top, 0px) + 108px)
    10px
    calc(env(safe-area-inset-bottom, 0px) + 28px);
}

.hm-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 32rem;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---------- Panel de registro ---------- */
.hm-panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: var(--hm-radius);
  padding: 14px 14px 12px;
  box-shadow: 0 10px 28px -12px rgba(15, 90, 50, 0.35), 0 1px 0 rgba(255, 255, 255, 0.8) inset;
}

.hm-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.hm-panel__titles { min-width: 0; }

.hm-eyebrow {
  display: block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #b45309;
}

.hm-title {
  margin: 2px 0 2px;
  font-size: 1.3rem;
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #14532d;
}

.hm-sub {
  font-size: 0.72rem;
  line-height: 1.3;
  color: var(--hm-muted);
}

/* Chip de estado de la jornada */
.hm-chip {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
  white-space: nowrap;
  background: #eef2f6;
  color: #475569;
}
.hm-chip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
.hm-chip--active { background: #dcfce7; color: #166534; }
.hm-chip--active .hm-chip__dot { animation: hm-pulse 1.8s ease-in-out infinite; }
.hm-chip--done { background: #e0f2fe; color: #0c4a6e; }

@keyframes hm-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.45; }
}

/* ---------- Línea de tiempo (Inicio → Actividades → Término) ---------- */
.hm-steps {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}

.hm-step {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 2px;
  min-width: 0;
}

/* conector con el siguiente paso */
.hm-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 13px;
  left: calc(50% + 17px);
  right: calc(-50% + 17px);
  height: 3px;
  border-radius: 3px;
  background: #d8e2dc;
}
.hm-step.is-done:not(:last-child)::after { background: #22c55e; }

.hm-step__dot {
  width: 27px;
  height: 27px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  background: #eef2f0;
  color: #64748b;
  border: 2px solid #d8e2dc;
  z-index: 1;
}
.hm-step__dot svg { width: 13px; height: 13px; }

.hm-step.is-current .hm-step__dot {
  background: #fff;
  color: #0a67ee;
  border-color: #0a67ee;
  box-shadow: 0 0 0 4px rgba(10, 103, 238, 0.14);
}
.hm-step.is-done .hm-step__dot {
  background: #22c55e;
  color: #fff;
  border-color: #22c55e;
}
.hm-step.is-locked .hm-step__dot {
  background: #f1f5f9;
  color: #94a3b8;
  border-color: #e2e8f0;
}

.hm-step__name {
  margin-top: 3px;
  font-size: 11px;
  font-weight: 700;
  color: var(--hm-ink);
}
.hm-step.is-locked .hm-step__name { color: #94a3b8; }

.hm-step__meta {
  font-size: 9.5px;
  color: var(--hm-muted);
  font-variant-numeric: tabular-nums;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- Selector segmentado ---------- */
.hm-segment {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 4px;
  border-radius: 16px;
  background: rgba(15, 42, 26, 0.07);
}

.hm-segment__thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc(50% - 4px);
  border-radius: 12px;
  background: linear-gradient(135deg, var(--hm-blue-a), var(--hm-blue-b));
  box-shadow: 0 6px 14px -4px rgba(10, 103, 238, 0.55);
  transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1), background 0.28s ease, opacity 0.2s ease;
  will-change: transform;
}
.hm-segment[data-active='actividades'] .hm-segment__thumb {
  transform: translateX(100%);
  background: linear-gradient(135deg, #a855f7, #7e22ce);
  box-shadow: 0 6px 14px -4px rgba(126, 34, 206, 0.55);
}
.hm-segment[data-active='none'] .hm-segment__thumb { opacity: 0; }

.hm-segment__btn {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 42px;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 700;
  color: #475569;
  cursor: pointer;
  transition: color 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}
.hm-segment__btn svg { width: 16px; height: 16px; flex: 0 0 auto; }
.hm-segment__btn.is-active { color: #fff; }
.hm-segment__btn.is-locked { color: #94a3b8; }
.hm-segment__lock { width: 12px !important; height: 12px !important; opacity: 0.9; }

/* ---------- Encabezado de sección ---------- */
.hm-section-head { padding: 2px 4px 0; }
.hm-section-head.is-center { text-align: center; padding-bottom: 6px; }
.hm-h2 {
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: #166534;
}
.hm-hint { font-size: 0.74rem; color: var(--hm-muted); }

/* ---------- Tarjetas de acción (Inicio / Término) ---------- */
.hm-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 8px;
}

.hm-action {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 232px;
  padding: 22px 10px 20px;
  border: 0;
  border-radius: var(--hm-radius);
  text-align: center;
  cursor: pointer;
  color: #fff;
  transition: transform 0.15s ease, box-shadow 0.25s ease, filter 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}
.hm-action:active:not(:disabled) { transform: scale(0.965); }
.hm-action:focus-visible { outline: 3px solid #0a67ee; outline-offset: 3px; }

/* --- disponible --- */
.hm-action--in.is-available {
  background: linear-gradient(150deg, var(--hm-blue-a) 0%, var(--hm-blue-b) 100%);
  box-shadow: 0 14px 26px -10px rgba(10, 103, 238, 0.65);
}
.hm-action--out.is-available {
  background: linear-gradient(150deg, var(--hm-red-a) 0%, var(--hm-red-b) 100%);
  box-shadow: 0 14px 26px -10px rgba(211, 27, 72, 0.6);
}

/* brillo que cruza la tarjeta (solo transform: barato para la GPU) */
.hm-action.is-available::after {
  content: '';
  position: absolute;
  inset: -30% auto -30% -60%;
  width: 45%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.28), transparent);
  transform: skewX(-20deg) translateX(0);
  animation: hm-sheen 5.5s ease-in-out infinite;
  pointer-events: none;
  z-index: -1;
}
@keyframes hm-sheen {
  0%, 55% { transform: skewX(-20deg) translateX(0); }
  100% { transform: skewX(-20deg) translateX(520%); }
}

.hm-action__icon {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  margin-bottom: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.24);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.12);
}
.hm-action__icon svg { width: 28px; height: 28px; }

.hm-action__title {
  font-size: 1rem;
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: 0.01em;
}
.hm-action__sub { font-size: 0.74rem; opacity: 0.9; }

.hm-action__cta {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.95);
  color: #0f172a;
}
.hm-action--in .hm-action__cta { color: #0a55c4; }
.hm-action--out .hm-action__cta { color: #b3123a; }
.hm-action__cta svg { width: 13px; height: 13px; }

/* --- completado --- */
.hm-action.is-done {
  cursor: default;
  color: #334155;
  background: #ffffff;
  box-shadow: 0 8px 20px -10px rgba(15, 42, 26, 0.35);
}
.hm-action--in.is-done { border: 1.5px solid rgba(10, 103, 238, 0.28); }
.hm-action--out.is-done { border: 1.5px solid rgba(211, 27, 72, 0.28); }

.hm-action__icon--done {
  color: #fff;
  border: 0;
  box-shadow: 0 8px 16px -6px rgba(0, 0, 0, 0.3);
}
.hm-action--in .hm-action__icon--done { background: linear-gradient(150deg, var(--hm-blue-a), var(--hm-blue-b)); }
.hm-action--out .hm-action__icon--done { background: linear-gradient(150deg, var(--hm-red-a), var(--hm-red-b)); }

.hm-action__time {
  font-size: 1.15rem;
  font-weight: 800;
  color: #0f2a1a;
  font-variant-numeric: tabular-nums;
}

/* --- bloqueado --- */
.hm-action.is-locked {
  cursor: not-allowed;
  color: #64748b;
  background: linear-gradient(180deg, #f8fafc, #eef2f6);
  border: 1.5px dashed rgba(100, 116, 139, 0.4);
  box-shadow: none;
}
.hm-action__icon--lock {
  background: #dfe5ec;
  border: 0;
  color: #64748b;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.08);
}
.hm-action.is-locked .hm-action__sub { color: #64748b; opacity: 1; }

/* --- etiquetas --- */
.hm-badge {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  padding: 4px 11px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.hm-badge--ok { background: #dcfce7; color: #166534; }
.hm-badge--lock { background: #475569; color: #fff; }

/* --- verificando --- */
.hm-action.is-loading { filter: saturate(0.6); cursor: progress; }
.hm-action__loader {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.45);
}
.hm-spinner {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 3px solid rgba(15, 42, 26, 0.18);
  border-top-color: #166534;
  animation: hm-rotate 0.75s linear infinite;
}
@keyframes hm-rotate { to { transform: rotate(360deg); } }

/* ---------- Información importante ---------- */
.hm-info {
  position: relative;
  overflow: hidden;
  margin-top: 12px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 18px;
  padding: 14px 14px 12px 18px;
  box-shadow: 0 8px 22px -12px rgba(15, 42, 26, 0.35);
}
.hm-info::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #f59e0b, #f97316, #ef4444);
}

.hm-info__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(15, 42, 26, 0.08);
}
.hm-info__badge {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #d97706;
  background: linear-gradient(135deg, #fffbeb, #ffedd5);
  border: 1px solid rgba(217, 119, 6, 0.22);
}
.hm-info__badge svg { width: 18px; height: 18px; }
.hm-info__title { font-size: 0.86rem; font-weight: 800; color: #1f2937; }
.hm-info__sub { font-size: 0.66rem; color: #6b7280; font-weight: 600; }

.hm-info__list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.hm-info__list li { display: flex; align-items: flex-start; gap: 10px; }
.hm-info__ico {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 8px;
}
.hm-info__ico svg { width: 14px; height: 14px; }
.hm-info__ico--blue { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
.hm-info__ico--red { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.hm-info__list strong { display: block; font-size: 0.76rem; line-height: 1.2; color: #1f2937; }
.hm-info__list li span:not(.hm-info__ico) { display: block; margin-top: 2px; font-size: 0.68rem; line-height: 1.35; color: #6b7280; }

/* ---------- Adaptación ---------- */
@media (max-width: 359px) {
  .hm-scroll { padding-left: 8px; padding-right: 8px; }
  .hm-title { font-size: 1.15rem; }
  .hm-chip { padding: 4px 8px; font-size: 9.5px; }
  .hm-action { min-height: 156px; padding: 12px 8px; }
  .hm-action__icon { width: 46px; height: 46px; }
  .hm-action__icon svg { width: 23px; height: 23px; }
  .hm-action__title { font-size: 0.9rem; }
  .hm-step__meta { font-size: 8.5px; }
}

@media (max-height: 640px) {
  .hm-action { min-height: 150px; }
}

@media (min-width: 768px) {
  .hm-container { max-width: 36rem; gap: 14px; }
  .hm-scroll { padding-top: calc(env(safe-area-inset-top, 0px) + 116px); }
  .hm-action { min-height: 196px; }
  .hm-title { font-size: 1.45rem; }
}

@media (prefers-reduced-motion: reduce) {
  .hm-action.is-available::after,
  .hm-chip--active .hm-chip__dot { animation: none; }
}


/* =====================================================================
   AJUSTES v2: info compacta + formulario de Actividades rediseñado
   (el paso 1 "Ubicación" conserva su diseño original)
   ===================================================================== */

/* ---------- Información importante: aviso compacto ---------- */
.hm-info {
  margin-top: 10px;
  padding: 9px 12px 9px 15px;
  border-radius: 14px;
  background: #fffaf0;
  border: 1px solid rgba(217, 119, 6, 0.2);
  box-shadow: none;
}
.hm-info::before { width: 3px; }
.hm-info__head { gap: 8px; padding-bottom: 7px; margin-bottom: 7px; border-bottom-color: rgba(217, 119, 6, 0.15); }
.hm-info__badge { width: 24px; height: 24px; border-radius: 8px; }
.hm-info__badge svg { width: 14px; height: 14px; }
.hm-info__title { font-size: 0.72rem; }
.hm-info__sub { display: none; }
.hm-info__list { gap: 6px; }
.hm-info__list li { gap: 8px; align-items: center; }
.hm-info__ico { width: 20px; height: 20px; border-radius: 6px; }
.hm-info__ico svg { width: 11px; height: 11px; }
.hm-info__list strong { font-size: 0.68rem; }
.hm-info__list li span:not(.hm-info__ico) { margin-top: 0; font-size: 0.6rem; line-height: 1.25; }

/* ---------- Actividades: contenedor sin "caja gigante" ---------- */
.hm-scroll > .apple-activities-container {
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  overflow: visible !important;
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hm-scroll > .apple-activities-container::before { display: none !important; }
.hm-scroll > .apple-activities-container > * { margin-top: 0 !important; margin-bottom: 0 !important; }

/* Encabezado + usuario: una franja compacta */
.hm-scroll > .apple-activities-container > .apple-header-card {
  padding: 11px 14px !important;
  border-radius: 16px !important;
  background: linear-gradient(135deg, #a855f7 0%, #7e22ce 100%) !important;
  box-shadow: 0 12px 22px -12px rgba(126, 34, 206, 0.7) !important;
}
.hm-scroll > .apple-activities-container .apple-header-title { font-size: 0.95rem !important; letter-spacing: 0 !important; }
.hm-scroll > .apple-activities-container > .apple-user-card {
  padding: 9px 12px !important;
  border-radius: 16px !important;
  background: #fff !important;
  border: 1px solid #f0e6fb !important;
  box-shadow: 0 6px 16px -10px rgba(76, 29, 149, 0.35) !important;
}

.hm-scroll > .apple-activities-container > form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hm-scroll > .apple-activities-container > form > * { margin-top: 0 !important; margin-bottom: 0 !important; }

/* Pasos 2-5: tarjetas planas y limpias (el 1 queda como estaba) */
.hm-scroll > .apple-activities-container > form > .apple-step-card-purple:not(:first-child) {
  background: #fff !important;
  border: 1px solid #efe6fa !important;
  border-radius: 18px !important;
  padding: 14px !important;
  box-shadow: 0 8px 20px -14px rgba(76, 29, 149, 0.4) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
.hm-scroll > .apple-activities-container > form > .apple-step-card-purple:not(:first-child) .apple-step-number-purple {
  width: 26px;
  height: 26px;
  border-radius: 9px !important;
  background: #f3e8ff !important;
  color: #7e22ce !important;
  box-shadow: none !important;
  font-size: 0.78rem;
  font-weight: 800;
}
.hm-scroll > .apple-activities-container > form > .apple-step-card-purple:not(:first-child) .apple-step-title {
  font-size: 0.9rem;
  font-weight: 800;
  color: #3b0764;
}

/* Campos */
.hm-scroll > .apple-activities-container .apple-select,
.hm-scroll > .apple-activities-container .apple-textarea,
.hm-scroll > .apple-activities-container .apple-input {
  border: 1.5px solid #e9d5ff !important;
  background: #faf7ff !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
.hm-scroll > .apple-activities-container .apple-select:focus,
.hm-scroll > .apple-activities-container .apple-textarea:focus,
.hm-scroll > .apple-activities-container .apple-input:focus {
  outline: none !important;
  border-color: #a855f7 !important;
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.16) !important;
}

/* Checklist: chips neutros con progreso (adiós al bloque amarillo) */
.hm-scroll > .apple-activities-container .apple-checklist-card {
  background: #fff !important;
  border: 1.5px dashed #d8b4fe !important;
  border-radius: 16px !important;
  padding: 11px 12px !important;
  box-shadow: none !important;
}
.hm-scroll > .apple-activities-container .apple-checklist-header { margin-bottom: 8px !important; }
.hm-scroll > .apple-activities-container .apple-checklist-icon { background: #f3e8ff !important; color: #7e22ce !important; box-shadow: none !important; }
.hm-scroll > .apple-activities-container .apple-checklist-title { color: #6b21a8 !important; font-size: 0.8rem !important; }
.hm-scroll > .apple-activities-container .apple-checklist-items { display: flex !important; flex-wrap: wrap; gap: 6px !important; }
.hm-scroll > .apple-activities-container .apple-checklist-item {
  flex: 0 0 auto;
  width: auto !important;
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  padding: 5px 10px !important;
  border-radius: 999px !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  background: #f4f4f5 !important;
  color: #71717a !important;
  border: 0 !important;
  box-shadow: none !important;
}
.hm-scroll > .apple-activities-container .apple-checklist-item-done { background: #dcfce7 !important; color: #166534 !important; }
.hm-scroll > .apple-activities-container .apple-checklist-circle { width: 14px !important; height: 14px !important; }

.hm-scroll > .apple-activities-container .apple-ready-card {
  background: #f0fdf4 !important;
  border: 1px solid #bbf7d0 !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  padding: 10px !important;
}

/* Botón guardar */
.hm-scroll > .apple-activities-container .glass-button-registro {
  border: 0 !important;
  border-radius: 16px !important;
  padding: 14px !important;
  font-size: 0.95rem !important;
  font-weight: 800 !important;
  color: #fff !important;
  background: linear-gradient(135deg, #a855f7 0%, #7e22ce 100%) !important;
  box-shadow: 0 14px 24px -12px rgba(126, 34, 206, 0.75) !important;
}
.hm-scroll > .apple-activities-container .glass-button-registro::before { display: none !important; }
.hm-scroll > .apple-activities-container .glass-button-registro:disabled {
  background: linear-gradient(135deg, #c4b5fd, #a78bfa) !important;
  box-shadow: none !important;
}

/* Botones de foto: estilo suave, acorde al resto */
.hm-scroll > .apple-activities-container .apple-photo-btn {
  background: #faf7ff !important;
  border: 1.5px solid #e9d5ff !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  color: #6b21a8 !important;
}
.hm-scroll > .apple-activities-container .apple-photo-btn:active { background: #f3e8ff !important; }
.hm-scroll > .apple-activities-container .apple-photo-btn-icon { background: #f3e8ff !important; color: #7e22ce !important; border: 0 !important; }
.hm-scroll > .apple-activities-container .apple-photo-btn-text { color: #6b21a8 !important; font-weight: 700; }

.hm-scroll > .apple-activities-container {
  width: 100%;
  max-width: 32rem;
  margin: 12px auto 0 !important;
  position: relative;
  z-index: 1;
}
@media (min-width: 768px) {
  .hm-scroll > .apple-activities-container { max-width: 36rem; }
}

/* =====================================================================
   v3: notas informativas, mensaje de estado y formulario de asistencia
   ===================================================================== */

/* ---------- Mensaje de estado (toast en línea) ---------- */
.hm-toast {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0 0;
  padding: 10px 14px 10px 10px;
  border-radius: 16px;
  font-size: 0.76rem;
  font-weight: 600;
  line-height: 1.3;
  background: #fff;
  border: 1px solid #e5e7eb;
  color: #334155;
  box-shadow: 0 10px 22px -14px rgba(15, 42, 26, 0.45);
}
.hm-toast__icon {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e2e8f0;
  color: #475569;
}
.hm-toast__icon svg { width: 14px; height: 14px; }
.hm-toast__spin {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2.5px solid currentColor;
  border-top-color: transparent;
  animation: hm-rotate 0.8s linear infinite;
}
.hm-toast--ok { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
.hm-toast--ok .hm-toast__icon { background: #22c55e; color: #fff; }
.hm-toast--error { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
.hm-toast--error .hm-toast__icon { background: #ef4444; color: #fff; }
.hm-toast--sync { background: #f0f9ff; border-color: #bae6fd; color: #0c4a6e; }
.hm-toast--sync .hm-toast__icon { background: #0ea5e9; color: #fff; }
.hm-toast--warn { background: #fffbeb; border-color: #fde68a; color: #92400e; }
.hm-toast--warn .hm-toast__icon { background: #f59e0b; color: #fff; }

.hm-toast-enter-active, .hm-toast-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.hm-toast-enter-from, .hm-toast-leave-to { opacity: 0; transform: translateY(-6px); }

/* ---------- Información importante: dos notas ---------- */
.hm-notes { margin-top: 16px; }
.hm-notes__label {
  margin: 0 2px 8px;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #6b7f74;
}
.hm-notes__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.hm-note {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 11px 12px 12px;
  border-radius: 16px;
  border: 1px solid transparent;
}
.hm-note strong { font-size: 0.74rem; line-height: 1.2; color: #0f172a; }
.hm-note__txt { font-size: 0.64rem; line-height: 1.3; color: #64748b; }
.hm-note__ico {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  margin-bottom: 3px;
}
.hm-note__ico svg { width: 13px; height: 13px; }
.hm-note--blue { background: linear-gradient(160deg, #eff6ff, #f8fbff); border-color: #dbeafe; }
.hm-note--blue .hm-note__ico { background: #dbeafe; color: #1d4ed8; }
.hm-note--rose { background: linear-gradient(160deg, #fff1f2, #fff8f8); border-color: #ffe4e6; }
.hm-note--rose .hm-note__ico { background: #ffe4e6; color: #be123c; }

@media (max-width: 340px) {
  .hm-notes__grid { grid-template-columns: 1fr; }
}

/* ---------- Formulario de ASISTENCIA (Inicio / Término) ---------- */
.hm-root .glass-card-blue,
.hm-root .glass-card-red {
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  overflow: visible !important;
}
.hm-root .glass-card-blue::before,
.hm-root .glass-card-red::before { display: none !important; }

.apple-attendance-container {
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  overflow: visible !important;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px !important;
}
.apple-attendance-container::before { display: none !important; }
.apple-attendance-container > * { margin-top: 0 !important; margin-bottom: 0 !important; }

.apple-attendance-container > .apple-header-card {
  padding: 11px 14px !important;
  border-radius: 16px !important;
}
.apple-attendance-container > .apple-header-entrada {
  background: linear-gradient(135deg, #3aa4ff 0%, #0a67ee 100%) !important;
  box-shadow: 0 12px 22px -12px rgba(10, 103, 238, 0.7) !important;
}
.apple-attendance-container > .apple-header-salida {
  background: linear-gradient(135deg, #ff5c7c 0%, #d31b48 100%) !important;
  box-shadow: 0 12px 22px -12px rgba(211, 27, 72, 0.7) !important;
}
.apple-attendance-container .apple-header-title { font-size: 0.95rem !important; letter-spacing: 0 !important; }

.apple-attendance-container > .apple-user-card {
  padding: 9px 12px !important;
  border-radius: 16px !important;
  background: #fff !important;
  border: 1px solid #e8eef7 !important;
  box-shadow: 0 6px 16px -10px rgba(15, 42, 26, 0.35) !important;
}

/* Pasos 2-3 (el 1, Ubicación, conserva su diseño) */
.apple-attendance-container > .apple-step-card:not(:nth-of-type(1)) {
  background: #fff !important;
  border: 1px solid #e8eef7 !important;
  border-radius: 18px !important;
  padding: 14px !important;
  box-shadow: 0 8px 20px -14px rgba(15, 42, 26, 0.4) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
.apple-attendance-container > .apple-step-card:not(:nth-of-type(1)) .apple-step-number {
  width: 26px;
  height: 26px;
  border-radius: 9px !important;
  background: #e0f2fe !important;
  color: #0a55c4 !important;
  box-shadow: none !important;
  font-size: 0.78rem;
  font-weight: 800;
}
.apple-attendance-container > .apple-step-card:not(:nth-of-type(1)) .apple-step-title {
  font-size: 0.9rem;
  font-weight: 800;
  color: #0f2a1a;
}

.apple-attendance-container .apple-textarea,
.apple-attendance-container .apple-input {
  border: 1.5px solid #dbe6f5 !important;
  background: #f8fbff !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
.apple-attendance-container .apple-textarea:focus,
.apple-attendance-container .apple-input:focus {
  outline: none !important;
  border-color: #3aa4ff !important;
  box-shadow: 0 0 0 3px rgba(58, 164, 255, 0.18) !important;
}

/* Botones de foto */
.apple-attendance-container .apple-photo-btn {
  background: #f8fbff !important;
  border: 1.5px solid #dbe6f5 !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  color: #0a55c4 !important;
}
.apple-attendance-container .apple-photo-btn:active { background: #eaf3ff !important; }
.apple-attendance-container .apple-photo-btn-icon { background: #e0f2fe !important; color: #0a67ee !important; border: 0 !important; }
.apple-attendance-container .apple-photo-btn-title { color: #0f2a1a !important; font-weight: 700; }
.apple-attendance-container .apple-photo-btn-subtitle { color: #64748b !important; }

/* Checklist: chips */
.apple-attendance-container .apple-checklist-card {
  background: #fff !important;
  border: 1.5px dashed #bcd3f0 !important;
  border-radius: 16px !important;
  padding: 11px 12px !important;
  box-shadow: none !important;
}
.apple-attendance-container .apple-checklist-header { margin-bottom: 8px !important; }
.apple-attendance-container .apple-checklist-icon { background: #e0f2fe !important; color: #0a55c4 !important; box-shadow: none !important; }
.apple-attendance-container .apple-checklist-title { color: #0a3d8f !important; font-size: 0.8rem !important; }
.apple-attendance-container .apple-checklist-items { display: flex !important; flex-wrap: wrap; gap: 6px !important; }
.apple-attendance-container .apple-checklist-item {
  flex: 0 0 auto;
  width: auto !important;
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  padding: 5px 10px !important;
  border-radius: 999px !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  background: #f4f4f5 !important;
  color: #71717a !important;
  border: 0 !important;
  box-shadow: none !important;
}
.apple-attendance-container .apple-checklist-done { background: #dcfce7 !important; color: #166534 !important; }
.apple-attendance-container .apple-checklist-check { width: 14px !important; height: 14px !important; }

.apple-attendance-container .apple-ready-card {
  background: #f0fdf4 !important;
  border: 1px solid #bbf7d0 !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  padding: 10px !important;
}

/* Botones de acción */
.apple-attendance-container .apple-action-buttons { display: flex; gap: 10px; }
.apple-attendance-container .apple-btn-cancel {
  flex: 0 0 34%;
  border-radius: 16px !important;
  padding: 14px 10px !important;
  font-weight: 700 !important;
  background: #f1f5f9 !important;
  color: #475569 !important;
  border: 0 !important;
  box-shadow: none !important;
}
.apple-attendance-container .apple-btn-submit {
  flex: 1 1 auto;
  border: 0 !important;
  border-radius: 16px !important;
  padding: 14px !important;
  font-weight: 800 !important;
  color: #fff !important;
}
.apple-attendance-container .apple-btn-entrada {
  background: linear-gradient(135deg, #3aa4ff, #0a67ee) !important;
  box-shadow: 0 14px 24px -12px rgba(10, 103, 238, 0.75) !important;
}
.apple-attendance-container .apple-btn-salida {
  background: linear-gradient(135deg, #ff5c7c, #d31b48) !important;
  box-shadow: 0 14px 24px -12px rgba(211, 27, 72, 0.75) !important;
}
.apple-attendance-container .apple-btn-disabled { filter: saturate(0.5); opacity: 0.55; box-shadow: none !important; }

/* Aire consistente en el formulario de Actividades */
.hm-scroll > .apple-activities-container { margin-top: 14px !important; }

/* =====================================================================
   v4: espaciado compacto + título y usuario unidos en una sola tarjeta
   ===================================================================== */

/* Menos aire entre bloques de los formularios */
.hm-scroll > .apple-activities-container,
.hm-scroll > .apple-activities-container > form,
.apple-attendance-container {
  gap: 8px !important;
}
.hm-scroll > .apple-activities-container { margin-top: 8px !important; }
.apple-attendance-container { margin-top: 4px !important; }

/* Tarjetas de pasos más compactas */
.hm-scroll > .apple-activities-container > form > .apple-step-card-purple:not(:first-child),
.apple-attendance-container > .apple-step-card:not(:nth-of-type(1)) {
  padding: 11px 12px !important;
  border-radius: 16px !important;
}
.hm-scroll > .apple-activities-container > form > .apple-step-card-purple,
.apple-attendance-container > .apple-step-card {
  margin-bottom: 0 !important;
}
.hm-scroll > .apple-activities-container .apple-checklist-card,
.apple-attendance-container .apple-checklist-card {
  padding: 9px 11px !important;
}
.hm-scroll > .apple-activities-container .apple-ready-card,
.apple-attendance-container .apple-ready-card {
  padding: 8px !important;
}

/* Título + usuario = una sola tarjeta (encabezado arriba, datos pegados abajo) */
.hm-scroll > .apple-activities-container > .apple-header-card,
.apple-attendance-container > .apple-header-card {
  border-radius: 18px 18px 0 0 !important;
  padding: 11px 14px 15px !important;
  position: relative;
  z-index: 0;
}
.hm-scroll > .apple-activities-container > .apple-header-card + .apple-user-card,
.apple-attendance-container > .apple-header-card + .apple-user-card {
  margin-top: -8px !important;      /* anula el gap: quedan pegadas */
  border-radius: 16px 16px 18px 18px !important;
  border-top: 0 !important;
  position: relative;
  z-index: 1;                        /* cubre la sombra del encabezado */
  padding: 10px 12px !important;
  box-shadow: 0 10px 20px -14px rgba(15, 42, 26, 0.45) !important;
}

/* =====================================================================
   v5: registros en UNA sola tarjeta (separadas por líneas desvanecidas),
   encabezado/usuario compactos, aviso único y anillo de carga GPS
   ===================================================================== */

/* ---------- Aviso (advertencia) ---------- */
.hm-alert {
  margin-top: 26px;
  padding: 0 14px 12px;
  border-radius: 16px;
  text-align: center;
  background: linear-gradient(180deg, #fffbeb 0%, #fff7dd 100%);
  border: 1px solid #fcd34d;
  color: #78350f;
}
.hm-alert__icon {
  width: 30px;
  height: 30px;
  margin: -15px auto 4px;               /* el círculo "monta" sobre el borde superior */
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #f59e0b;
  color: #fff;
  border: 3px solid #fffbeb;
  box-shadow: 0 6px 12px -4px rgba(245, 158, 11, 0.7);
}
.hm-alert__icon svg { width: 15px; height: 15px; }
.hm-alert__title {
  margin: 0 0 3px;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #b45309;
}
.hm-alert__text {
  margin: 0;
  font-size: 0.68rem;
  line-height: 1.4;
  text-align: justify;
  text-align-last: center;
  hyphens: auto;
}

/* ---------- Tarjeta única: contenedor ---------- */
.hm-scroll > .apple-activities-container,
.apple-attendance-container {
  --hm-line: rgba(126, 34, 206, 0.32);
  background: #fff !important;
  border: 1px solid rgba(15, 42, 26, 0.08) !important;
  border-radius: 20px !important;
  overflow: hidden !important;
  box-shadow: 0 14px 30px -18px rgba(15, 42, 26, 0.5) !important;
  padding: 0 !important;
  gap: 0 !important;
}
.apple-attendance-container.hm-tone-in { --hm-line: rgba(10, 103, 238, 0.32); }
.apple-attendance-container.hm-tone-out { --hm-line: rgba(211, 27, 72, 0.32); }

/* El formulario de actividades también se apila sin huecos */
.hm-scroll > .apple-activities-container > form { gap: 0 !important; }

/* Encabezado compacto, a sangre completa */
.hm-scroll > .apple-activities-container > .apple-header-card,
.apple-attendance-container > .apple-header-card {
  border-radius: 0 !important;
  padding: 8px 14px !important;
  box-shadow: none !important;
  margin: 0 !important;
}
.hm-scroll > .apple-activities-container .apple-header-title,
.apple-attendance-container .apple-header-title { font-size: 0.85rem !important; }
.hm-scroll > .apple-activities-container .apple-header-icon,
.apple-attendance-container .apple-header-icon { width: 26px !important; height: 26px !important; border-radius: 8px !important; }
.hm-scroll > .apple-activities-container .apple-header-icon svg,
.apple-attendance-container .apple-header-icon svg { width: 15px !important; height: 15px !important; }

/* Usuario: fila compacta unida al encabezado */
.hm-scroll > .apple-activities-container > .apple-header-card + .apple-user-card,
.apple-attendance-container > .apple-header-card + .apple-user-card {
  margin: 0 !important;
  border-radius: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 8px 12px !important;
}
.hm-scroll > .apple-activities-container .apple-avatar,
.apple-attendance-container .apple-avatar {
  width: 32px !important;
  height: 32px !important;
  border-width: 2px !important;
}
.hm-scroll > .apple-activities-container .apple-avatar-initials,
.apple-attendance-container .apple-avatar-initials { font-size: 0.7rem !important; }
.hm-scroll > .apple-activities-container .apple-user-name,
.apple-attendance-container .apple-user-name { font-size: 0.8rem !important; line-height: 1.15 !important; }
.hm-scroll > .apple-activities-container .apple-user-role,
.apple-attendance-container .apple-user-role { font-size: 0.64rem !important; }
.hm-scroll > .apple-activities-container .apple-status-badge,
.apple-attendance-container .apple-status-badge { font-size: 0.6rem !important; padding: 3px 9px !important; }

/* Pasos, checklist y "listo": sin marco propio; separados por línea desvanecida */
.hm-root .hm-scroll > .apple-activities-container > form > .apple-step-card-purple,
.hm-root .hm-scroll > .apple-activities-container > form > .apple-checklist-card,
.hm-root .hm-scroll > .apple-activities-container > form > .apple-ready-card,
.hm-root .apple-attendance-container > .apple-step-card,
.hm-root .apple-attendance-container > .apple-checklist-card,
.hm-root .apple-attendance-container > .apple-ready-card,
.hm-root .apple-attendance-container > .apple-action-buttons {
  background: linear-gradient(90deg, transparent 0%, var(--hm-line) 50%, transparent 100%) top / 100% 1px no-repeat !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  padding: 11px 14px !important;
  margin: 0 !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
.hm-root .hm-scroll > .apple-activities-container > form > .apple-checklist-card,
.hm-root .hm-scroll > .apple-activities-container > form > .apple-ready-card,
.hm-root .apple-attendance-container > .apple-checklist-card,
.hm-root .apple-attendance-container > .apple-ready-card {
  padding: 9px 14px !important;
}
.hm-scroll > .apple-activities-container .apple-checklist-item,
.apple-attendance-container .apple-checklist-item { padding: 4px 9px !important; }
.hm-root .apple-attendance-container > .apple-action-buttons { padding: 10px 14px 12px !important; }

/* Botón guardar dentro de la tarjeta */
.hm-scroll > .apple-activities-container > form > button {
  width: auto !important;
  margin: 2px 14px 14px !important;
  display: block;
}
.hm-scroll > .apple-activities-container > form > button.glass-button-registro { width: calc(100% - 28px) !important; }

/* Mensaje de bloqueo dentro del contenedor */
.hm-scroll > .apple-activities-container > .apple-warning-card { margin: 10px 14px 0 !important; }

/* ---------- Anillo de carga del GPS ---------- */
.apple-location-btn,
.apple-location-wrapper { overflow: visible !important; }
.apple-location-ring { display: none !important; }
.apple-location-btn-loading { animation: none !important; }
.apple-location-btn-loading::before,
.apple-location-btn-loading::after {
  content: "";
  position: absolute;
  inset: -7px;
  border-radius: 50%;
  pointer-events: none;
}
/* pista tenue */
.apple-location-btn-loading::after {
  border: 4px solid rgba(10, 103, 238, 0.14);
}
/* arco giratorio pegado al borde */
.apple-location-btn-loading::before {
  z-index: 1;
  background: conic-gradient(from 0deg, rgba(10,103,238,0) 0deg, rgba(10,103,238,0) 90deg, #3aa4ff 200deg, #0a67ee 330deg, rgba(10,103,238,0) 360deg);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 4px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 4px));
  animation: hm-gps-spin 1s linear infinite;
  will-change: transform;
}
@keyframes hm-gps-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .apple-location-btn-loading::before { animation-duration: 2.4s; }
}


.hm-syncbar {
  position: fixed;
  z-index: 39;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: calc(100vw - 48px);
  padding: 4px 14px 5px;
  border-radius: 0 0 14px 14px;
  font-size: 0.66rem;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #0284c7, #0369a1);
  box-shadow: 0 8px 16px -8px rgba(3, 105, 161, 0.7);
}
.hm-syncbar span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hm-syncbar .hm-toast__spin { width: 10px; height: 10px; border-width: 2px; flex: none; }
.hm-sync-enter-active, .hm-sync-leave-active { transition: opacity 0.22s ease, transform 0.22s ease; }
.hm-sync-enter-from, .hm-sync-leave-to { opacity: 0; transform: translate(-50%, -100%); }
</style>
