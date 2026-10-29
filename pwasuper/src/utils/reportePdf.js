/**
 * Generador del PDF del reporte (diseño institucional).
 * Mismo archivo en admin-pwa y pwasuper: si se modifica uno, copiarlo al otro.
 */
import jsPDF from 'jspdf'
import QRCode from 'qrcode'
import logoBienestar from '../assets/images/logo-bienestar.png?inline'
import logoSV from '../assets/images/logo-sembrando-vida.png?inline'
import { fechaDeReporteTexto } from './fechaReporte'

const PW = 210
const PH = 297
const M = 16
const CW = PW - 2 * M
const BOTTOM = PH - 41            // ultima pagina: deja libre el QR y el pie
const BOTTOM_TABLA = PH - 26      // paginas intermedias: aprovecha todo el espacio hasta el pie
const VERIFICAR_URL = 'https://app.sembrandodatos.com/verificar/'

const GUINDA = [97, 18, 50]
const DORADO = [201, 162, 39]
const TEXTO = [31, 41, 55]
const GRIS_TXT = [107, 114, 128]
const GRIS_FONDO = [243, 241, 239]
const LINEA = [216, 210, 204]
const BLANCO = [255, 255, 255]
const CREMA = [250, 248, 246]

const fill = (d, c) => d.setFillColor(c[0], c[1], c[2])
const draw = (d, c) => d.setDrawColor(c[0], c[1], c[2])
const color = (d, c) => d.setTextColor(c[0], c[1], c[2])

function cabecera(doc) {
  // Logos oficiales a color: Bienestar a la izquierda y Sembrando Vida a la derecha, a la misma altura,
  // centrados en una franja baja y pegados al contenido (sin hueco arriba ni abajo).
  const top = 8
  const band = 13
  const mid = top + band / 2
  const h = 10.5
  const dim = (img) => { const pr = doc.getImageProperties(img); return h * pr.width / pr.height }
  doc.addImage(logoBienestar, 'PNG', M, mid - h / 2, dim(logoBienestar), h)
  const ws = dim(logoSV)
  doc.addImage(logoSV, 'PNG', PW - M - ws, mid - h / 2, ws, h)
  const yl = top + band + 3
  draw(doc, GUINDA); doc.setLineWidth(0.6); doc.line(M, yl, PW - M, yl)
  draw(doc, DORADO); doc.setLineWidth(0.25); doc.line(M, yl + 1.2, PW - M, yl + 1.2)
  return yl + 1.2
}

function tituloInstitucional(doc, y, principal, sub) {
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9.5); color(doc, TEXTO)
  doc.text('SECRETARÍA DE BIENESTAR', PW / 2, y, { align: 'center' })
  doc.setFontSize(7.8); color(doc, GRIS_TXT)
  doc.text('SUBSECRETARÍA DE INCLUSIÓN PRODUCTIVA Y DESARROLLO RURAL', PW / 2, y + 4.6, { align: 'center' })
  draw(doc, LINEA); doc.setLineWidth(0.2); doc.line(PW / 2 - 22, y + 7.6, PW / 2 + 22, y + 7.6)
  doc.setFontSize(13); color(doc, GUINDA)
  doc.text(principal, PW / 2, y + 13.4, { align: 'center' })
  let fin = y + 13.4
  if (sub) {
    // Etiqueta suave con el mes del reporte
    const t = sub.toUpperCase()
    doc.setFont('helvetica', 'bold'); doc.setFontSize(7)
    const tw = doc.getTextWidth(t) + 11.5
    const px = PW / 2 - tw / 2
    fill(doc, [251, 246, 248]); draw(doc, [234, 218, 224]); doc.setLineWidth(0.25)
    doc.roundedRect(px, y + 16.6, tw, 5.2, 2.6, 2.6, 'FD')
    draw(doc, [150, 70, 95]); doc.setLineWidth(0.3)
    const cx = px + 3.9
    doc.roundedRect(cx - 1.2, y + 17.8, 2.4, 2.6, 0.4, 0.4, 'S')
    doc.line(cx - 1.2, y + 18.8, cx + 1.2, y + 18.8)
    color(doc, [122, 31, 61])
    doc.text(t, PW / 2 + 1.8, y + 20.3, { align: 'center' })
    fin = y + 21.8
  }
  return fin
}

function pie(doc, folio, n, total, qrData, huella) {
  doc.setPage(n)
  draw(doc, DORADO); doc.setLineWidth(0.25); doc.line(M, PH - 19.5, PW - M, PH - 19.5)
  draw(doc, GUINDA); doc.setLineWidth(0.6); doc.line(M, PH - 18.3, PW - M, PH - 18.3)
  doc.setFont('helvetica', 'normal'); doc.setFontSize(7.2); color(doc, TEXTO)
  doc.text('Paseo de la Reforma # 116, Piso 16, Col. Juárez, Alc. Cuauhtémoc, CDMX C.P. 06600', PW / 2, PH - 13.2, { align: 'center' })
  const tel = 'Tel.: (55) 5328 5000   '
  const web = 'www.gob.mx/bienestar'
  const wt = doc.getTextWidth(tel)
  const ww = doc.getTextWidth(web)
  const x0 = PW / 2 - (wt + ww) / 2
  doc.text(tel, x0, PH - 9.6)
  color(doc, GUINDA)
  doc.textWithLink(web, x0 + wt, PH - 9.6, { url: 'https://www.gob.mx/bienestar' })
  doc.setFontSize(7); color(doc, GRIS_TXT)
  if (folio) doc.text(`Folio ${folio}`, M, PH - 9.6)
  doc.text(`Página ${n} de ${total}`, PW - M, PH - 9.6, { align: 'right' })
  if (qrData && n === total) {
    doc.addImage(qrData, 'PNG', PW - M - 14, PH - 38, 14, 14)
    doc.setFontSize(5.5)
    doc.text('Verifica este reporte', PW - M, PH - 21.6, { align: 'right' })
    if (huella) {
      doc.setFont('helvetica', 'bold'); doc.setFontSize(5.5); color(doc, GRIS_TXT)
      doc.text('HUELLA DE INTEGRIDAD', PW - M - 17, PH - 31.6, { align: 'right' })
      doc.setFont('courier', 'bold'); doc.setFontSize(7.6); color(doc, TEXTO)
      doc.text(huella, PW - M - 17, PH - 27.6, { align: 'right' })
    }
  }
}

function altoTexto(doc, texto, ancho, size, interlineado) {
  doc.setFontSize(size)
  return doc.splitTextToSize(String(texto || ''), ancho).length * interlineado
}

function cuadriculaDatos(doc, y, filas) {
  // filas: [[etiqueta1, valor1, etiqueta2, valor2], ...]
  const wl1 = 38, wv1 = 54, wl2 = 24, wv2 = CW - wl1 - wv1 - wl2
  const xs = [M, M + wl1, M + wl1 + wv1, M + wl1 + wv1 + wl2]
  const ws = [wl1, wv1, wl2, wv2]
  let yy = y
  const alturas = filas.map((f) => {
    let l = 1
    f.forEach((t, i) => {
      doc.setFont('helvetica', i % 2 === 0 ? 'bold' : 'normal'); doc.setFontSize(i % 2 === 0 ? 7 : 8.2)
      l = Math.max(l, doc.splitTextToSize(String(t), ws[i] - 6).length)
    })
    return Math.max(8, l * 3.8 + 4)
  })
  const total = alturas.reduce((a, b) => a + b, 0)
  draw(doc, LINEA); doc.setLineWidth(0.25)
  fill(doc, GRIS_FONDO)
  doc.rect(xs[0], y, wl1, total, 'F'); doc.rect(xs[2], y, wl2, total, 'F')
  doc.rect(M, y, CW, total, 'S')
  filas.forEach((f, r) => {
    const h = alturas[r]
    if (r > 0) doc.line(M, yy, M + CW, yy)
    f.forEach((t, i) => {
      const esEt = i % 2 === 0
      doc.setFont('helvetica', esEt ? 'bold' : 'normal'); doc.setFontSize(esEt ? 7 : 8.2)
      color(doc, esEt ? GUINDA : TEXTO)
      const lineas = doc.splitTextToSize(String(t), ws[i] - 6)
      const bloque = lineas.length * 3.8
      doc.text(lineas, xs[i] + 3, yy + (h - bloque) / 2 + 3, { baseline: 'alphabetic' })
    })
    yy += h
  })
  draw(doc, LINEA)
  doc.line(xs[1], y, xs[1], y + total); doc.line(xs[2], y, xs[2], y + total); doc.line(xs[3], y, xs[3], y + total)
  return y + total
}

function encabezadoTabla(doc, y, cols) {
  fill(doc, GUINDA); doc.rect(M, y, CW, 7.5, 'F')
  doc.setFont('helvetica', 'bold'); doc.setFontSize(7.8); color(doc, BLANCO)
  let x = M
  const nombres = ['No.', 'Fecha', 'Tipo', 'Hora', 'Actividad desarrollada']
  cols.forEach((w, i) => { doc.text(nombres[i], x + w / 2, y + 5, { align: 'center' }); x += w })
  return y + 7.5
}

async function fotoABase64(act, apiUrl) {
  try {
    if (act.foto_base64) return act.foto_base64.startsWith('data:') ? act.foto_base64 : 'data:image/jpeg;base64,' + act.foto_base64
    if (act.foto_url) {
      let nombre = act.foto_url
      if (nombre.includes('/fotos/')) nombre = nombre.split('/fotos/').pop()
      else if (nombre.includes('fotos/')) nombre = nombre.split('fotos/').pop()
      const r = await fetch(`${apiUrl}/fotos-base64/${nombre}`)
      if (!r.ok) return null
      const j = await r.json()
      return j && j.success && j.data ? j.data : null
    }
  } catch (e) { /* sin foto */ }
  return null
}

function seleccionarImagenes(acts, max) {
  const out = []
  const dias = new Set()
  const orden = [...acts].sort((a, b) => new Date(b.fecha_hora) - new Date(a.fecha_hora))
  for (const a of orden) {
    if (out.length >= max) break
    const dia = new Date(a.fecha_hora).toISOString().split('T')[0]
    if (!dias.has(dia)) { out.push(a); dias.add(dia) }
  }
  for (const a of orden) {
    if (out.length >= max) break
    if (!out.includes(a)) out.push(a)
  }
  return out
}

// Reune hasta 6 evidencias (3 de campo y 3 de gabinete, de dias distintos) que SI se pueden cargar.
// Las fotos que ya no existen en el servidor se saltan y se prueba con la siguiente actividad.
async function cargarEvidencias(actividades, apiUrl) {
  const conFoto = actividades.filter((a) => a.foto_url || a.foto_base64)
  if (!conFoto.length) return []
  const esTipo = (a, t) => (a.tipo_actividad || 'campo').toLowerCase() === t
  const colas = {
    campo: seleccionarImagenes(conFoto.filter((a) => esTipo(a, 'campo')), 60),
    gabinete: seleccionarImagenes(conFoto.filter((a) => esTipo(a, 'gabinete')), 60)
  }
  const res = { campo: [], gabinete: [] }
  let intentos = 0
  const llenar = async (tipo, meta) => {
    while (res[tipo].length < meta && colas[tipo].length && intentos < 40) {
      const lote = colas[tipo].splice(0, meta - res[tipo].length)
      intentos += lote.length
      const fotos = await Promise.all(lote.map((a) => fotoABase64(a, apiUrl)))
      lote.forEach((a, i) => { if (fotos[i]) res[tipo].push({ a, foto: fotos[i] }) })
    }
  }
  await Promise.all([llenar('campo', 3), llenar('gabinete', 3)])
  // si falta de un tipo, se completa hasta 6 con el otro
  const faltan = 6 - res.campo.length - res.gabinete.length
  if (faltan > 0) {
    await llenar('campo', res.campo.length + faltan)
    const faltan2 = 6 - res.campo.length - res.gabinete.length
    if (faltan2 > 0) await llenar('gabinete', res.gabinete.length + faltan2)
  }
  return [...res.campo, ...res.gabinete].slice(0, 6)
}

function bloqueFirmas(doc, y, ctx) {
  const { usuario, firmaUsuario, firmaSupervisor, nombreSupervisor, facilitadorNombre, esFacilitador } = ctx
  const colW = (CW - 14) / 2
  const xs = [M, M + colW + 14]
  const imgW = 52, imgH = 20
  const roles = ['ELABORÓ', 'REVISÓ Y AUTORIZÓ']
  const firmas = [firmaUsuario, firmaSupervisor]
  const nombres = [usuario.nombre || 'Sin nombre', nombreSupervisor || facilitadorNombre || usuario.supervisor || 'Sin asignar']
  const cargoSup = esFacilitador
    ? ['Facilitador Comunitario']
    : ['Encargada de Despacho de la Coordinación', 'Territorial ' + (usuario.territorio || '')]
  const cargos = [[usuario.cargo || 'Facilitador Comunitario'], cargoSup]
  roles.forEach((rol, i) => {
    const cx = xs[i] + colW / 2
    doc.setFont('helvetica', 'bold'); doc.setFontSize(7.4); color(doc, GRIS_TXT)
    doc.text(rol, cx, y, { align: 'center' })
    if (firmas[i]) {
      try { doc.addImage(firmas[i], 'PNG', cx - imgW / 2, y + 2, imgW, imgH) } catch (e) { /* firma no disponible */ }
    }
    draw(doc, TEXTO); doc.setLineWidth(0.3)
    doc.line(xs[i] + 4, y + imgH + 4, xs[i] + colW - 4, y + imgH + 4)
    doc.setFont('helvetica', 'bold'); doc.setFontSize(8.2); color(doc, TEXTO)
    const nom = doc.splitTextToSize(String(nombres[i]), colW - 8)
    doc.text(nom, cx, y + imgH + 9, { align: 'center' })
    let yy = y + imgH + 9 + nom.length * 3.6
    doc.setFont('helvetica', 'normal'); doc.setFontSize(7.4); color(doc, GRIS_TXT)
    cargos[i].forEach((t) => { doc.text(String(t), cx, yy + 0.4, { align: 'center' }); yy += 3.6 })
  })
  return y + imgH + 9 + 4 * 3.6
}
const ALTO_FIRMAS = 20 + 9 + 3 * 3.6 + 2

/**
 * @param {Object} datos datos_reporte (usuario, periodo, actividades, folio opcional)
 * @param {Object} o { firmaUsuario, firmaSupervisor, nombreSupervisor, facilitadorNombre, esFacilitador, fechaFirma, apiUrl }
 * @returns {Promise<string>} PDF en base64 (sin prefijo data:)
 */
const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
function etiquetaMes(periodo) {
  const nombre = periodo.mesNombre || (Number.isInteger(periodo.mes) ? MESES[periodo.mes] : '')
  return `${nombre || ''} ${periodo.anio || ''}`.trim()
}

export async function generarPDFReporte(datos, o = {}) {
  const usuario = datos.usuario || {}
  const periodo = datos.periodo || {}
  const folio = datos.folio || null
  const huella = o.huella || null
  const codigoVerif = o.codigoVerificacion || null
  const ctx = {
    usuario,
    firmaUsuario: o.firmaUsuario || null,
    firmaSupervisor: o.firmaSupervisor || null,
    nombreSupervisor: o.nombreSupervisor || null,
    facilitadorNombre: o.facilitadorNombre || null,
    esFacilitador: !!o.esFacilitador
  }
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  doc.setLineHeightFactor(1.3)
  const evid = await cargarEvidencias(datos.actividades || [], o.apiUrl || '')

  // ---------- Página 1 ----------
  let y = cabecera(doc)
  y = tituloInstitucional(doc, y + 11, 'FORMATO DE SEGUIMIENTO A ACTIVIDADES PROGRAMADAS', etiquetaMes(periodo))
  y += 8
  doc.setFont('helvetica', 'bold'); doc.setFontSize(8); color(doc, GUINDA)
  if (folio) doc.text(`FOLIO  ${folio}`, M, y)
  doc.setFont('helvetica', 'normal'); color(doc, TEXTO)
  doc.text('Fecha de emisión:  ' + fechaDeReporteTexto(periodo, ctx.firmaSupervisor ? o.fechaFirma : null), PW - M, y, { align: 'right' })
  y += 4

  const mes = periodo.mes !== undefined ? periodo.mes : 0
  const anio = periodo.anio || new Date().getFullYear()
  const ini = new Date(anio, mes, 1).toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' })
  const fin = new Date(anio, mes + 1, 0).toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' })
  y = cuadriculaDatos(doc, y, [
    ['PRESTADOR DE SERVICIOS', usuario.nombre || 'Sin nombre', 'CURP', usuario.curp || 'No registrado'],
    ['CARGO', usuario.cargo || '—', 'PERIODO', `Del ${ini} al ${fin}`],
    ['PROGRAMA', 'SEMBRANDO VIDA', 'TERRITORIO', usuario.territorio || 'No asignado']
  ])
  y += 9

  // ---------- Actividades ----------
  const actividades = datos.actividades || []
  const cols = [12, 34, 20, 15, CW - 81]
  doc.setFont('helvetica', 'bold'); doc.setFontSize(9); color(doc, GUINDA)
  doc.text('ACTIVIDADES REALIZADAS', M, y)
  y += 3
  y = encabezadoTabla(doc, y, cols)

  const SIZE = 7.6
  const LH = SIZE * 1.3 * 0.3528
  actividades.forEach((a, idx) => {
    const desc = a.descripcion || a.categoria_actividad || 'Actividad de ' + (a.tipo_actividad || 'campo')
    doc.setFont('helvetica', 'normal'); doc.setFontSize(SIZE)
    const lineas = doc.splitTextToSize(String(desc), cols[4] - 6)
    const h = Math.max(9, lineas.length * LH + 5)
    if (y + h > BOTTOM_TABLA) {
      doc.addPage()
      y = cabecera(doc) + 9
      y = encabezadoTabla(doc, y, cols)
    }
    fill(doc, idx % 2 === 0 ? BLANCO : CREMA)
    doc.rect(M, y, CW, h, 'F')
    draw(doc, LINEA); doc.setLineWidth(0.2); doc.line(M, y + h, M + CW, y + h)
    doc.line(M, y, M, y + h); doc.line(M + CW, y, M + CW, y + h)
    const f = a.fecha_hora ? new Date(a.fecha_hora) : new Date()
    const fecha = f.toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
    const hora = f.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false })
    const tipo = (a.tipo_actividad || 'campo').charAt(0).toUpperCase() + (a.tipo_actividad || 'campo').slice(1)
    color(doc, TEXTO); doc.setFont('helvetica', 'normal'); doc.setFontSize(SIZE)
    const cy = y + h / 2 + 1
    let x = M
    doc.text(String(idx + 1), x + cols[0] / 2, cy, { align: 'center' }); x += cols[0]
    doc.text(fecha, x + cols[1] / 2, cy, { align: 'center' }); x += cols[1]
    doc.text(tipo, x + cols[2] / 2, cy, { align: 'center' }); x += cols[2]
    doc.text(hora, x + cols[3] / 2, cy, { align: 'center' }); x += cols[3]
    const bloque = lineas.length * LH
    doc.text(String(desc), x + 3, y + (h - bloque) / 2 + 2.6, { maxWidth: cols[4] - 6, align: 'justify' })
    y += h
  })
  if (actividades.length === 0) {
    fill(doc, CREMA); doc.rect(M, y, CW, 14, 'F'); draw(doc, LINEA); doc.rect(M, y, CW, 14, 'S')
    doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5); color(doc, GRIS_TXT)
    doc.text('Sin actividades registradas en este periodo', PW / 2, y + 8.5, { align: 'center' })
    y += 14
  }

  // ---------- Firmas ----------
  y += 14
  if (y + ALTO_FIRMAS > BOTTOM_TABLA) { doc.addPage(); y = cabecera(doc) + 16 }
  y = bloqueFirmas(doc, y, ctx)

  // ---------- Evidencias fotográficas ----------
  {
  doc.addPage()
  y = cabecera(doc)
  y = tituloInstitucional(doc, y + 11, 'EVIDENCIAS FOTOGRÁFICAS DE ACTIVIDADES', etiquetaMes(periodo))
  y += 7

  // Franja del prestador
  fill(doc, GRIS_FONDO); draw(doc, LINEA); doc.setLineWidth(0.25)
  doc.roundedRect(M, y, CW, 13, 2, 2, 'FD')
  doc.setFont('helvetica', 'bold'); doc.setFontSize(8.6); color(doc, TEXTO)
  doc.text(String(usuario.nombre || 'Sin nombre'), M + 4, y + 5.4)
  doc.setFont('helvetica', 'normal'); doc.setFontSize(7.6); color(doc, GRIS_TXT)
  doc.text(`CURP ${usuario.curp || 'No registrado'}  ·  ${usuario.cargo || ''}  ·  ${usuario.territorio || 'No asignado'}`, M + 4, y + 9.8, { maxWidth: CW - 40 })
  y += 13 + 7

  if (!evid.length) {
    // Aviso profesional cuando las fotografías ya no están disponibles
    const ch = 58
    fill(doc, [251, 248, 246]); draw(doc, LINEA); doc.setLineWidth(0.25)
    doc.roundedRect(M, y, CW, ch, 3, 3, 'FD')
    const cx = PW / 2
    const cy = y + 17
    fill(doc, [243, 230, 234]); doc.circle(cx, cy, 8.5, 'F')
    draw(doc, GUINDA); doc.setLineWidth(0.4)
    doc.roundedRect(cx - 4.6, cy - 2.8, 9.2, 6.6, 1.2, 1.2, 'S')
    doc.circle(cx, cy + 0.5, 1.9, 'S')
    doc.lines([[0.8, -1.4], [2, 0], [0.8, 1.4]], cx - 1.8, cy - 2.8, [1, 1], 'S')
    draw(doc, [180, 69, 95]); doc.setLineWidth(0.45)
    doc.line(cx - 5.2, cy + 4.6, cx + 5.2, cy - 3.8)
    doc.setFont('helvetica', 'bold'); doc.setFontSize(11); color(doc, GUINDA)
    doc.text('Evidencias fotográficas no disponibles', cx, y + 33, { align: 'center' })
    doc.setFont('helvetica', 'normal'); doc.setFontSize(8.4); color(doc, TEXTO)
    doc.text('Las fotografías de las actividades de este periodo ya no se encuentran almacenadas en el sistema,', cx, y + 39.5, { align: 'center' })
    doc.text('por lo que no se incluyen en este reporte.', cx, y + 44.2, { align: 'center' })
    doc.setFontSize(7.6); color(doc, GRIS_TXT)
    doc.text('El registro de cada actividad se conserva en el apartado "Actividades realizadas".', cx, y + 51.5, { align: 'center' })
    y += ch
  } else {
    const fotos = evid.map((e) => e.foto)
    const seleccion = evid.map((e) => e.a)
    const gap = 5
    const cw3 = (CW - 2 * gap) / 3
    const ih = cw3 * 0.66
    const ch = ih + 16
    seleccion.forEach((a, i) => {
      const col = i % 3
      const row = Math.floor(i / 3)
      const x = M + col * (cw3 + gap)
      const top = y + row * (ch + 6)
      fill(doc, BLANCO); draw(doc, LINEA); doc.setLineWidth(0.25)
      doc.roundedRect(x, top, cw3, ch, 2, 2, 'FD')
      const ix = x + 1.4, iy = top + 1.4, iw = cw3 - 2.8, ihh = ih - 1.4
      fill(doc, GRIS_FONDO); doc.rect(ix, iy, iw, ihh, 'F')
      if (fotos[i]) {
        try {
          const p = doc.getImageProperties(fotos[i])
          const esc = Math.max(iw / p.width, ihh / p.height)
          const w = p.width * esc, h = p.height * esc
          doc.saveGraphicsState()
          doc.rect(ix, iy, iw, ihh, null)
          doc.clip(); doc.discardPath()
          doc.addImage(fotos[i], p.fileType || 'JPEG', ix + (iw - w) / 2, iy + (ihh - h) / 2, w, h)
          doc.restoreGraphicsState()
        } catch (e) { /* imagen no valida */ }
      } else {
        doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5); color(doc, GRIS_TXT)
        doc.text('Imagen no disponible', ix + iw / 2, iy + ihh / 2, { align: 'center' })
      }
      // etiqueta de tipo
      const campoT = (a.tipo_actividad || 'campo').toLowerCase() === 'campo'
      const txt = campoT ? 'CAMPO' : 'GABINETE'
      doc.setFont('helvetica', 'bold'); doc.setFontSize(6.2)
      const cwid = doc.getTextWidth(txt) + 5
      if (campoT) fill(doc, [47, 125, 79]); else fill(doc, [107, 74, 143])
      doc.roundedRect(x + 3, top + 3, cwid, 4.6, 2.3, 2.3, 'F')
      color(doc, BLANCO)
      doc.text(txt, x + 3 + cwid / 2, top + 6.1, { align: 'center' })
      // pie de la tarjeta
      const desc = String(a.descripcion || a.categoria_actividad || 'Actividad de ' + (a.tipo_actividad || 'campo'))
      doc.setFont('helvetica', 'bold'); doc.setFontSize(7); color(doc, TEXTO)
      let l = doc.splitTextToSize(desc, cw3 - 6)
      if (l.length > 2) { l = l.slice(0, 2); l[1] = l[1].replace(/\s*\S{0,3}$/, '') + '…' }
      doc.text(l, x + 3, top + ih + 4.2)
      const fh = a.fecha_hora ? new Date(a.fecha_hora) : null
      if (fh) {
        doc.setFont('helvetica', 'normal'); doc.setFontSize(6.6); color(doc, GRIS_TXT)
        doc.text(fh.toLocaleDateString('es-MX') + ' · ' + fh.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false }), x + 3, top + ch - 2.6)
      }
    })
    y += Math.ceil(seleccion.length / 3) * (ch + 6)
  }

  y += evid.length ? 6 : 14
  if (y + ALTO_FIRMAS > BOTTOM) { doc.addPage(); y = cabecera(doc) + 16 }
  bloqueFirmas(doc, y, ctx)
  }

  // ---------- Pie en todas las páginas ----------
  let qrData = null
  if (folio) {
    try { qrData = await QRCode.toDataURL(VERIFICAR_URL + folio + (codigoVerif ? '?c=' + codigoVerif : ''), { margin: 0, width: 240, errorCorrectionLevel: 'M' }) } catch (e) { /* sin QR */ }
  }
  const total = doc.internal.getNumberOfPages()
  for (let n = 1; n <= total; n++) pie(doc, folio, n, total, qrData, huella)

  return doc.output('datauristring').split(',')[1]
}
