import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/Login.vue'
import Home from '../views/Home.vue'

// Inicio y acceso van con la app; el resto se descarga al visitarlas (y se precarga en segundo plano)
const Register = () => import('../views/Register.vue')
const ForgotPassword = () => import('../views/ForgotPassword.vue')
const Historial = () => import('../views/Historial.vue')
const Profile = () => import('../views/Profile.vue')
const Notificaciones = () => import('../views/Notificaciones.vue')
const Manuales = () => import('../views/Manuales.vue')
const Support = () => import('../views/Support.vue')
const Settings = () => import('../views/Settings.vue')
const Reportes = () => import('../views/Reportes.vue')

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },
  { path: '/forgot-password', name: 'ForgotPassword', component: ForgotPassword },
  { path: '/reset-password', name: 'ResetPassword', component: ForgotPassword },
  { path: '/historial', name: 'Historial', component: Historial },
  { path: '/profile', name: 'Profile', component: Profile },
  { path: '/notificaciones', name: 'Notificaciones', component: Notificaciones },
  { path: '/manuales', name: 'Manuales', component: Manuales },
  { path: '/support', name: 'Support', component: Support },
  { path: '/settings', name: 'Settings', component: Settings },
  { path: '/reportes', name: 'Reportes', component: Reportes },
  // Cualquier otra dirección (/index.html, enlaces viejos, errores de escritura) lleva al Inicio: nunca pantalla vacía
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Guard de navegación para proteger rutas
router.beforeEach((to, from, next) => {
  // Enlaces antiguos con # (por ejemplo /#/historial) se convierten en rutas normales
  if (to.hash && to.hash.startsWith('#/')) {
    return next({ path: to.hash.slice(1), replace: true })
  }
  const user = localStorage.getItem('user')
  const isLoggedIn = !!user
  
  // Si intenta acceder a login, register o forgot-password y ya está logueado, redirigir a home
  if ((to.name === 'Login' || to.name === 'Register' || to.name === 'ForgotPassword') && isLoggedIn) {
    next({ name: 'Home' })
  }
  // Si intenta acceder a rutas protegidas sin estar logueado, redirigir a login
  else if ((to.name === 'Home' || to.name === 'Historial' || to.name === 'Profile' || to.name === 'Notificaciones' || to.name === 'Manuales' || to.name === 'Support' || to.name === 'Settings' || to.name === 'Reportes') && !isLoggedIn) {
    next({ name: 'Login' })
  }
  // En cualquier otro caso, permitir la navegación
  else {
    next()
  }
})

// Si tras una actualización falta un archivo de una pantalla (versión vieja en memoria),
// se recarga una sola vez para tomar la versión nueva en lugar de quedarse en blanco.
router.onError((error, to) => {
  const msg = String((error && error.message) || error)
  if (!/dynamically imported module|Importing a module script failed|Loading chunk|Failed to fetch|Load failed/i.test(msg)) return
  if (navigator.onLine && !sessionStorage.getItem('chunk-reload')) {
    sessionStorage.setItem('chunk-reload', '1')
    window.location.assign(to && to.fullPath ? to.fullPath : '/')
  } else {
    router.replace('/').catch(() => {}) // sin internet: Inicio siempre está disponible
  }
})
router.afterEach(() => sessionStorage.removeItem('chunk-reload'))

// Descarga en segundo plano las pantallas más usadas cuando el teléfono está libre y la red lo permite
export function precargarPantallas() {
  const c = navigator.connection || {}
  if (c.saveData || /(^|-)2g$/.test(c.effectiveType || '')) return
  const tarea = () => [Profile, Notificaciones, Manuales, Support, Settings].forEach((f) => f().catch(() => {}))
  if ('requestIdleCallback' in window) requestIdleCallback(tarea, { timeout: 8000 })
  else setTimeout(tarea, 4000)
}

export default router
