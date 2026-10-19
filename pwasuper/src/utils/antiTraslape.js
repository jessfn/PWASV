// Evita que un elemento se encime con otro sin importar el zoom, el tamaño de letra o el contenido:
// mide en vivo hasta dónde llegan las barras fijas y publica esas medidas como variables CSS.
//   --app-top-h : borde inferior de la barra verde superior
//   --hdr-bottom: borde inferior del encabezado fijo de la vista (Notificaciones, Manuales, Reportes)
// Las vistas usan estas variables para empezar siempre justo debajo, en vez de adivinar una altura fija.

export function iniciarMedidaEncabezados() {
  const raiz = document.documentElement
  let pendiente = false
  let enlazados = []

  const medir = () => {
    pendiente = false
    // El título vive dentro del bloque superior: su borde inferior es el del propio bloque
    const barra = document.querySelector('.app-top')
    const abajo = barra ? Math.ceil(barra.getBoundingClientRect().bottom) + 'px' : '0px'
    raiz.style.setProperty('--app-top-h', abajo)
    if (raiz.classList.contains('has-vt')) raiz.style.setProperty('--hdr-bottom', abajo)
    else raiz.style.removeProperty('--hdr-bottom')
    const encabezado = barra

    // Si cambió el encabezado o la barra (otra vista), se vuelven a observar
    const actuales = [barra, encabezado, ...(encabezado ? Array.from(encabezado.children) : [])].filter(Boolean)
    if (observador && (actuales.length !== enlazados.length || actuales.some((e, i) => e !== enlazados[i]))) {
      observador.disconnect()
      actuales.forEach((e) => observador.observe(e))
      enlazados = actuales
    }
  }

  const pedir = () => {
    if (pendiente) return
    pendiente = true
    requestAnimationFrame(medir)
  }

  const observador = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(pedir) : null
  const app = document.getElementById('app')
  if (app && typeof MutationObserver !== 'undefined') new MutationObserver(pedir).observe(app, { childList: true, subtree: true })
  window.addEventListener('resize', pedir)
  window.addEventListener('load', pedir)
  pedir()
}
