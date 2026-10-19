// Última información de cada pantalla, guardada en el teléfono.
// Sirve para abrir las vistas al instante con lo último que se vio y actualizar en segundo plano
// (también deja ver los datos sin internet). Se guarda por persona para no mezclar cuentas.

const PRE = 'cv_'
const MAX_CHARS = 900000   // ~1 MB: si una lista es más grande simplemente no se guarda

const uid = () => {
  try { return (JSON.parse(localStorage.getItem('user') || 'null') || {}).id || '0' } catch { return '0' }
}

export function cacheLeer(clave) {
  try {
    const t = localStorage.getItem(`${PRE}${uid()}_${clave}`)
    return t ? JSON.parse(t).d : null
  } catch {
    return null
  }
}

export function cacheGuardar(clave, datos) {
  try {
    const t = JSON.stringify({ d: datos, t: Date.now() })
    if (t.length < MAX_CHARS) localStorage.setItem(`${PRE}${uid()}_${clave}`, t)
  } catch { /* sin espacio: no pasa nada */ }
}
