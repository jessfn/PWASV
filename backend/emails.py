"""Plantillas de correo de Sembrando Vida (HTML con estilos en línea, compatibles con Gmail/Outlook).

Diseño alineado a la app: degradado verde, tarjeta blanca, botón grande y mensajes cortos.
"""
from html import escape

LOGO_URL = "https://app.sembrandodatos.com/pwa-192x192.png"
VERDE_OSCURO = "#0b3d24"
VERDE = "#16a34a"
FONDO = "#eef8f1"


def _primer_nombre(nombre):
    n = (nombre or "").strip().split()
    return n[0].capitalize() if n else ""


def _layout(titulo, subtitulo, cuerpo, preheader, anio):
    """Estructura común: encabezado verde, tarjeta de contenido y pie."""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">
<title>{escape(titulo)}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{FONDO};">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};padding:26px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
    <tr><td style="background:#0f5132;background-image:linear-gradient(135deg,{VERDE_OSCURO} 0%,#0f5132 55%,{VERDE} 100%);border-radius:22px 22px 0 0;padding:30px 30px 26px;font-family:'Segoe UI',Arial,sans-serif;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="vertical-align:middle;"><img src="{LOGO_URL}" width="46" height="46" alt="" style="display:block;border-radius:13px;border:2px solid rgba(255,255,255,.55);"></td>
        <td style="vertical-align:middle;padding-left:12px;font-family:'Segoe UI',Arial,sans-serif;">
          <div style="color:#ffffff;font-size:15px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;line-height:1.2;">Sembrando Vida</div>
          <div style="color:#bfeacd;font-size:12.5px;font-weight:600;letter-spacing:.02em;line-height:1.4;margin-top:2px;">Aplicación de Seguimiento</div>
        </td>
      </tr></table>
      <div style="color:#ffffff;font-size:26px;line-height:1.2;font-weight:800;margin-top:20px;">{escape(titulo)}</div>
      <div style="color:#d4f3df;font-size:14px;line-height:1.5;margin-top:6px;">{escape(subtitulo)}</div>
    </td></tr>
    <tr><td style="background:#ffffff;border-radius:0 0 22px 22px;padding:28px 30px 30px;font-family:'Segoe UI',Arial,sans-serif;color:#1b2a22;font-size:15px;line-height:1.65;border:1px solid #d6e8dc;border-top:0;">
      {cuerpo}
    </td></tr>
    <tr><td align="center" style="padding:18px 10px 4px;font-family:'Segoe UI',Arial,sans-serif;color:#7b8f84;font-size:12px;line-height:1.6;">
      Mensaje automático de <b style="color:#0f5132;">Sembrando Vida · Aplicación de Seguimiento</b><br>Por favor no respondas a este correo.<br>
      &copy; {anio} Sembrando Vida · app.sembrandodatos.com
    </td></tr>
  </table>
</td></tr></table></body></html>"""


def _boton(texto, link):
    # Botón "a prueba de Outlook": tabla con fondo sólido + enlace
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:26px auto 8px;"><tr>
<td align="center" style="background:#0f5132;background-image:linear-gradient(135deg,#0f5132,{VERDE});border-radius:14px;">
<a href="{escape(link)}" style="display:inline-block;padding:16px 34px;font-family:'Segoe UI',Arial,sans-serif;font-size:16px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:14px;">{escape(texto)}</a>
</td></tr></table>"""


def _chip(texto):
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:6px auto 0;"><tr>
<td style="background:#ecfdf3;border:1px solid #bbf7d0;border-radius:999px;padding:6px 14px;font-family:'Segoe UI',Arial,sans-serif;font-size:12.5px;font-weight:700;color:#166534;">{escape(texto)}</td>
</tr></table>"""


def correo_reset(nombre, link, minutos, anio):
    """Correo con la liga para crear una nueva contraseña. Devuelve (asunto, texto, html)."""
    saludo = _primer_nombre(nombre)
    hola = f"Hola {escape(saludo)}," if saludo else "Hola,"
    cuerpo = f"""
<p style="margin:0 0 12px;font-size:16px;font-weight:700;color:#0b3d24;">{hola}</p>
<p style="margin:0 0 6px;text-align:justify;">Recibimos una solicitud para crear una nueva contraseña de tu cuenta. Presiona el botón y elige la contraseña que quieras usar.</p>
{_boton("Crear nueva contraseña", link)}
{_chip(f"Vence en {minutos} minutos · Un solo uso")}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:26px 0 0;"><tr>
<td style="background:#f4faf6;border:1px solid #d6e8dc;border-radius:14px;padding:14px 16px;font-size:13.5px;line-height:1.6;color:#3b4d43;">
<b style="color:#0f5132;">¿No fuiste tú?</b><br>Ignora este mensaje: tu contraseña actual no cambiará y la liga dejará de funcionar sola.
</td></tr></table>
<p style="margin:22px 0 0;font-size:12px;line-height:1.6;color:#8a9b92;">Si el botón no abre, copia y pega esta dirección en tu navegador:<br>
<a href="{escape(link)}" style="color:#15803d;word-break:break-all;">{escape(link)}</a></p>"""
    html = _layout("Recupera tu contraseña", "Es rápido: solo dos pasos.", cuerpo,
                   f"Crea tu nueva contraseña. La liga vence en {minutos} minutos.", anio)
    texto = (f"{hola}\n\nRecibimos una solicitud para crear una nueva contraseña de tu cuenta de Sembrando Vida.\n\n"
             f"Abre esta liga (vence en {minutos} minutos y es de un solo uso):\n{link}\n\n"
             "Si no fuiste tú, ignora este mensaje: tu contraseña no cambiará.\n\n— Sembrando Vida")
    return "Recupera tu contraseña · Sembrando Vida", texto, html


def correo_cambio(nombre, fecha_texto, anio):
    """Aviso de que la contraseña fue cambiada. Devuelve (asunto, texto, html)."""
    saludo = _primer_nombre(nombre)
    hola = f"Hola {escape(saludo)}," if saludo else "Hola,"
    cuerpo = f"""
<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:0 auto 14px;"><tr>
<td align="center" style="width:64px;height:64px;background:#dcfce7;border-radius:32px;font-size:34px;line-height:64px;color:#16a34a;font-weight:800;">&#10003;</td></tr></table>
<p style="margin:0 0 12px;font-size:16px;font-weight:700;color:#0b3d24;text-align:center;">{hola}</p>
<p style="margin:0 0 6px;text-align:center;">Tu contraseña se cambió correctamente el<br><b style="color:#0f5132;">{escape(fecha_texto)}</b>.</p>
<p style="margin:14px 0 0;text-align:center;">Ya puedes iniciar sesión con tu nueva contraseña.</p>
{_boton("Ir a la aplicación", "https://app.sembrandodatos.com/login")}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:22px 0 0;"><tr>
<td style="background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:14px 16px;font-size:13.5px;line-height:1.6;color:#7c3a0e;">
<b>¿No fuiste tú?</b><br>Avisa de inmediato a tu facilitador o a tu coordinación para proteger tu cuenta.
</td></tr></table>"""
    html = _layout("Contraseña actualizada", "Tu cuenta está protegida.", cuerpo, "Tu contraseña fue cambiada correctamente.", anio)
    texto = (f"{hola}\n\nTu contraseña de Sembrando Vida se cambió correctamente el {fecha_texto}.\n"
             "Si no fuiste tú, avisa de inmediato a tu facilitador o coordinación.\n\n— Sembrando Vida")
    return "Tu contraseña fue cambiada · Sembrando Vida", texto, html
