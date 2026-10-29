// Fecha que se imprime en el reporte ("Fecha:"), segun el periodo que cubre:
//  - Mes ya terminado  -> ultimo dia de ese mes (30/31, 28/29), sin importar cuando se genere, descargue o firme.
//  - Mes en curso      -> si ya esta firmado, el dia de la firma (fija); si no, el dia de hoy.
//  - Mes futuro        -> hoy.
export function fechaDeReporte(periodo, fechaFirma = null, hoy = new Date()) {
  const mes = periodo && Number.isInteger(periodo.mes) ? periodo.mes : null
  const anio = periodo && Number(periodo.anio) ? Number(periodo.anio) : null
  if (mes === null || anio === null) return fechaFirma ? new Date(fechaFirma) : hoy
  const ultimoDia = new Date(anio, mes + 1, 0)
  const inicioMesSiguiente = new Date(anio, mes + 1, 1)
  if (hoy >= inicioMesSiguiente) return ultimoDia
  const f = fechaFirma ? new Date(fechaFirma) : null
  if (f && !isNaN(f) && f.getFullYear() === anio && f.getMonth() === mes) return f
  return hoy
}

export function fechaDeReporteTexto(periodo, fechaFirma = null, hoy = new Date()) {
  return fechaDeReporte(periodo, fechaFirma, hoy).toLocaleDateString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
