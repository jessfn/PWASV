/**
 * Genera el PDF de un reporte desde sus datos estructurados (datos_reporte).
 * El diseño vive en ./reportePdf.js (el mismo archivo que usa pwasuper).
 */
import { generarPDFReporte } from './reportePdf'

const API_URL = import.meta.env.VITE_API_URL || 'https://apipwa.sembrandodatos.com'

/**
 * @returns {Promise<string>} PDF en base64 (sin prefijo data:)
 */
export async function generarPDFDesdesDatos(datos, firmaUsuario, firmaSupervisor, nombreSupervisor, facilitadorNombre = null, fechaFirma = null, folio = null) {
  return generarPDFReporte(folio ? { ...datos, folio } : datos, {
    firmaUsuario,
    firmaSupervisor,
    nombreSupervisor,
    facilitadorNombre,
    esFacilitador: !!(facilitadorNombre && String(facilitadorNombre).trim()),
    fechaFirma,
    apiUrl: API_URL
  })
}
