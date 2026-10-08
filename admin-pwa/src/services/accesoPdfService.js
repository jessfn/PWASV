import { jsPDF } from 'jspdf'

const URL_ADMIN = 'https://adminpwa.sembrandodatos.com/'

// Sin caracteres ambiguos (0/O, 1/l/I)
const ALFABETO = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'

/** Contraseña temporal de 8 caracteres con al menos una letra y un número. */
export function generarContrasena(largo = 8) {
  const azar = (n) => {
    const a = new Uint32Array(1)
    crypto.getRandomValues(a)
    return a[0] % n
  }
  let pwd = ''
  for (let i = 0; i < largo; i++) pwd += ALFABETO[azar(ALFABETO.length)]
  if (!/\d/.test(pwd)) pwd = pwd.slice(0, -1) + '23456789'[azar(8)]
  if (!/[a-zA-Z]/.test(pwd)) pwd = 'k' + pwd.slice(1)
  return pwd
}

const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]
const mezcla = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t))

/**
 * Genera y descarga el PDF de acceso de un usuario administrativo.
 * Nada se superpone: encabezado arriba, tarjeta debajo, nota y pie.
 */
export function descargarPdfAcceso({ username, password, nombre }) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const W = 210
  const M = 22 // margen lateral

  // ---- Encabezado con degradado (franjas finas) ----
  const H = 92
  const c1 = hex('#0b3d24')
  const c2 = hex('#16a34a')
  const franjas = 70
  for (let i = 0; i < franjas; i++) {
    const [r, g, b] = mezcla(c1, c2, i / (franjas - 1))
    doc.setFillColor(r, g, b)
    doc.rect(0, (H / franjas) * i, W, H / franjas + 0.3, 'F')
  }
  // Círculos decorativos dentro del encabezado
  doc.setFillColor(40, 130, 85)
  doc.circle(172, 26, 16, 'F')
  doc.setFillColor(30, 110, 70)
  doc.circle(190, 70, 9, 'F')

  // Etiqueta
  doc.setDrawColor(255, 255, 255)
  doc.setLineWidth(0.3)
  doc.roundedRect(M, 18, 44, 7, 3.5, 3.5, 'S')
  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(7.5)
  doc.text('SEMBRANDO VIDA', M + 7, 22.6, { charSpace: 0.6 })

  // Título
  doc.setFontSize(27)
  doc.text('Acceso al Panel', M, 50)
  doc.text('Administrativo', M, 62)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10.5)
  doc.setTextColor(215, 240, 224)
  doc.text('Sistema de seguimiento y administración de registros.', M, 76)

  // ---- Tarjeta de credenciales (debajo del encabezado, sin tocarlo) ----
  const filas = [
    { k: 'DIRECCIÓN DE ACCESO', v: URL_ADMIN, mono: false, size: 12.5, enlace: true },
    { k: 'USUARIO', v: username, mono: true, size: 17 },
    { k: 'CONTRASEÑA', v: password, mono: true, size: 17 },
  ]
  if (nombre) filas.unshift({ k: 'TITULAR', v: nombre, mono: false, size: 12.5 })

  const filaH = 22
  const cardY = H + 14
  const cardH = 14 + filas.length * filaH - 4
  const cardW = W - M * 2
  // Sombra suave
  doc.setFillColor(232, 240, 235)
  doc.roundedRect(M + 0.8, cardY + 1.6, cardW, cardH, 5, 5, 'F')
  // Tarjeta
  doc.setFillColor(255, 255, 255)
  doc.setDrawColor(220, 235, 226)
  doc.setLineWidth(0.4)
  doc.roundedRect(M, cardY, cardW, cardH, 5, 5, 'FD')

  let y = cardY + 13
  filas.forEach((f, i) => {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(7.5)
    doc.setTextColor(21, 128, 61)
    doc.text(f.k, M + 10, y, { charSpace: 0.7 })

    doc.setFont(f.mono ? 'courier' : 'helvetica', 'bold')
    doc.setFontSize(f.size)
    doc.setTextColor(11, 61, 36)
    if (f.enlace) doc.textWithLink(f.v, M + 10, y + 8, { url: URL_ADMIN })
    else doc.text(f.v, M + 10, y + 8)

    if (i < filas.length - 1) {
      doc.setDrawColor(230, 241, 234)
      doc.setLineWidth(0.3)
      doc.line(M + 10, y + 13, W - M - 10, y + 13)
    }
    y += filaH
  })

  // ---- Nota ----
  const notaY = cardY + cardH + 14
  const nota =
    'Esta información es personal y confidencial; no la compartas con terceras personas. ' +
    'Se recomienda ingresar desde Google Chrome o Microsoft Edge y cerrar la sesión al terminar. ' +
    'Por seguridad, cambia tu contraseña en cuanto ingreses por primera vez.'
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(93, 111, 101)
  const lineas = doc.splitTextToSize(nota, cardW - 8)
  doc.setFillColor(22, 163, 74)
  doc.rect(M, notaY - 3.6, 0.9, lineas.length * 4.6 + 0.6, 'F')
  doc.text(nota, M + 5, notaY, { maxWidth: cardW - 8, align: 'justify', lineHeightFactor: 1.5 })

  // ---- Pie ----
  doc.setDrawColor(227, 239, 231)
  doc.setLineWidth(0.3)
  doc.line(M, 282, W - M, 282)
  doc.setFontSize(8)
  doc.setTextColor(138, 155, 146)
  doc.text('adminpwa.sembrandodatos.com', M, 287)
  doc.text('Documento de uso interno', W - M, 287, { align: 'right' })

  const limpio = String(username).replace(/[^a-zA-Z0-9_-]/g, '')
  doc.save(`Acceso_${limpio}.pdf`)
}
