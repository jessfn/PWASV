// Documentos adjuntos: cómo se reconocen, se abren y se guardan en el dispositivo.
// Idea (igual que WhatsApp o Gmail): una tarjeta con el tipo de documento y dos acciones claras:
//   - Abrir: PDF e imágenes se ven en el visor del propio dispositivo; Word, Excel y PowerPoint se pasan a
//     la app que los abre (hoja "Compartir/Abrir con…" del teléfono) o se guardan si el dispositivo no la tiene.
//   - Guardar: descarga el archivo con su nombre correcto.

const TIPOS = {
  pdf:   { clave: 'pdf',   etiqueta: 'Documento PDF',        corto: 'PDF', color: '#b91c1c', fondo: '#fde8e8', mime: 'application/pdf' },
  word:  { clave: 'word',  etiqueta: 'Documento de Word',    corto: 'DOC', color: '#1d4fa8', fondo: '#e3ecfb', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
  excel: { clave: 'excel', etiqueta: 'Hoja de Excel',        corto: 'XLS', color: '#0f6b33', fondo: '#dcf3e4', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  ppt:   { clave: 'ppt',   etiqueta: 'Presentación',         corto: 'PPT', color: '#b4470f', fondo: '#fdeadb', mime: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' },
  texto: { clave: 'texto', etiqueta: 'Documento de texto',   corto: 'TXT', color: '#475467', fondo: '#eceff3', mime: 'text/plain' },
  zip:   { clave: 'zip',   etiqueta: 'Archivo comprimido',   corto: 'ZIP', color: '#6d3fb5', fondo: '#efe6fb', mime: 'application/zip' },
  otro:  { clave: 'otro',  etiqueta: 'Archivo adjunto',      corto: 'ARCH', color: '#475467', fondo: '#eceff3', mime: 'application/octet-stream' },
}

const POR_EXT = {
  pdf: 'pdf', doc: 'word', docx: 'word', odt: 'word', rtf: 'word',
  xls: 'excel', xlsx: 'excel', csv: 'excel', ods: 'excel',
  ppt: 'ppt', pptx: 'ppt', odp: 'ppt',
  txt: 'texto', zip: 'zip', rar: 'zip', '7z': 'zip',
}
const POR_TIPO = { pdf: 'pdf', documento: 'word', excel: 'excel', presentacion: 'ppt', texto: 'texto' }

/** Reconoce el tipo por la columna `archivo_tipo` del servidor o por la extensión del nombre. */
export function tipoDocumento(archivoTipo, archivoNombre) {
  const t = String(archivoTipo || '').toLowerCase()
  if (POR_TIPO[t]) return TIPOS[POR_TIPO[t]]
  if (POR_EXT[t]) return TIPOS[POR_EXT[t]]
  const ext = String(archivoNombre || '').toLowerCase().split('.').pop()
  return TIPOS[POR_EXT[ext] || 'otro']
}

export function tamanoLegible(bytes) {
  const n = Number(bytes)
  if (!n || n < 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

/** Tamaño del archivo sin descargarlo (cabecera Content-Length). */
export async function tamanoRemoto(url) {
  try {
    const r = await fetch(url, { method: 'HEAD' })
    return r.ok ? Number(r.headers.get('content-length')) || 0 : 0
  } catch {
    return 0
  }
}

/** Descarga el archivo a memoria con avance (0-100). */
export async function bajarArchivo(url, tipo, alAvance) {
  const r = await fetch(url)
  if (!r.ok) throw new Error('No se pudo descargar el archivo')
  const total = Number(r.headers.get('content-length')) || 0
  if (!r.body || !total || !alAvance) return new Blob([await r.arrayBuffer()], { type: tipo.mime })
  const lector = r.body.getReader()
  const partes = []
  let recibido = 0
  for (;;) {
    const { done, value } = await lector.read()
    if (done) break
    partes.push(value)
    recibido += value.length
    alAvance(Math.min(99, Math.round((recibido * 100) / total)))
  }
  alAvance(100)
  return new Blob(partes, { type: tipo.mime })
}

/** Guarda el archivo en el dispositivo con un nombre correcto. */
export function guardarBlob(blob, nombre) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

/** Nombre de archivo para descargar (con su extensión). */
export function nombreDescarga(archivoNombre, tipo, base = 'documento') {
  const limpio = String(archivoNombre || '').replace(/[\\/:*?"<>|]+/g, ' ').trim()
  if (limpio && /\.[A-Za-z0-9]{2,5}$/.test(limpio)) return limpio
  const ext = { pdf: 'pdf', word: 'docx', excel: 'xlsx', ppt: 'pptx', texto: 'txt', zip: 'zip' }[tipo.clave] || 'bin'
  return `${limpio || base}.${ext}`
}

/** ¿Este dispositivo puede pasar el archivo a otra app (hoja Compartir / Abrir con…)? */
export function puedeCompartirArchivo(blob, nombre) {
  try {
    if (!navigator.canShare || !navigator.share) return false
    return navigator.canShare({ files: [new File([blob], nombre, { type: blob.type })] })
  } catch {
    return false
  }
}

export async function compartirArchivo(blob, nombre, titulo) {
  const archivo = new File([blob], nombre, { type: blob.type })
  await navigator.share({ files: [archivo], title: titulo || nombre })
}

/** Abre un PDF o imagen en el visor del dispositivo (pestaña nueva) usando una copia local. */
export function abrirEnVisor(blob) {
  const url = URL.createObjectURL(blob)
  const w = window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 120000)
  return !!w
}
