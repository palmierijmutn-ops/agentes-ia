import html
import os
import re
import smtplib
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser

# ---------------------------------------------------------------------------
# Configuración y Credenciales
# ---------------------------------------------------------------------------
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASS")
RECIPIENT_EMAIL = "jpalmieri@frba.utn.edu.ar"

# User-Agent para evitar errores 403 Forbidden por parte de los servidores
HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# Directorio de feeds RSS / Atom
# ---------------------------------------------------------------------------
FEEDS_INNOVACION_EDUCATIVA = {
    # --- PORTALES DE LATINOAMÉRICA ---
    "Observatorio Tec de Monterrey": "https://observatorio.tec.mx/feed/",
    "Eduteka (Universidad Icesi)": "https://eduteka.icesi.edu.co/rss",
    "RELPE (Red Latinoamericana)": "https://relpe.org/feed/",

    # --- PORTALES DE EUROPA ---
    "INTEF (Blog Principal)": "https://intef.es/feed/",
    "INTEF (Observatorio de Tecnología)": "https://intef.es/observatorio/feed/",
    "Educación 3.0": "https://www.educaciontrespuntocero.com/feed/",
    "EDUforics (Fundación SM)": "https://www.eduforics.com/es/feed/",
    "European Schoolnet Academy": "https://www.europeanschoolnetacademy.eu/rss"
}

# ---------------------------------------------------------------------------
# Funciones Auxiliares
# ---------------------------------------------------------------------------
def limpiar_texto(html_text: str) -> str:
    """Elimina etiquetas HTML, normaliza entidades y espacios."""
    if not html_text:
        return "Sin descripción disponible."
    texto = re.sub(r"<[^>]+>", " ", html_text)
    texto = html.unescape(texto)
    palabras = texto.split()
    return " ".join(palabras)

def truncar_a_tres_lineas(texto: str, max_palabras: int = 40) -> str:
    """Trunca el texto para que ocupe aproximadamente tres renglones."""
    palabras = texto.split()
    if len(palabras) > max_palabras:
        return " ".join(palabras[:max_palabras]) + "..."
    return texto

def es_enlace_valido(url: str, timeout: int = 8) -> bool:
    """
    Verifica de manera autónoma si la URL responde satisfactoriamente (HTTP 200, 301, 302).
    Utiliza cabeceras de navegador para prevenir bloqueos 403.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False

    # Intento primario con método HEAD (más rápido y ligero)
    try:
        req = urllib.request.Request(url, headers=HEADERS_NAVEGADOR, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status in (200, 301, 302)
    except Exception:
        pass

    # Intento secundario con GET (muchos servidores rechazan o bloquean peticiones HEAD)
    try:
        req = urllib.request.Request(url, headers=HEADERS_NAVEGADOR, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status in (200, 301, 302)
    except Exception:
        return False

def obtener_fecha_entrada(entry) -> datetime | None:
    """Extrae y convierte published_parsed o updated_parsed a objeto datetime UTC."""
    tiempo_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tiempo_struct:
        try:
            return datetime.fromtimestamp(time.mktime(tiempo_struct), tz=timezone.utc)
        except Exception:
            return None
    return None

# ---------------------------------------------------------------------------
# Lógica de Recopilación y Curaduría
# ---------------------------------------------------------------------------
def recopilar_articulos_semanales():
    """Descarga los feeds, filtra publicaciones de los últimos 7 días y verifica enlaces."""
    ahora_utc = datetime.now(timezone.utc)
    limite_semanal = ahora_utc - timedelta(days=7)
    
    articulos_recolectados = {}

    for portal, feed_url in FEEDS_INNOVACION_EDUCATIVA.items():
        print(f"Consultando feed: {portal}...")
        try:
            # Se pasa el encabezado User-Agent a feedparser para evitar rechazo 403
            parsed = feedparser.parse(
                feed_url,
                request_headers=HEADERS_NAVEGADOR
            )
        except Exception as e:
            print(f"  [!] Error al analizar el canal {portal}: {e}")
            continue

        entradas_validas = []

        for entry in parsed.entries:
            fecha_publicacion = obtener_fecha_entrada(entry)
            
            # Filtro cronológico estricto: solo entradas de los últimos 7 días
            if fecha_publicacion and fecha_publicacion < limite_semanal:
                continue

            link = getattr(entry, "link", None)
            if not link:
                continue

            # Verificación de conectividad del enlace
            if not es_enlace_valido(link):
                print(f"  [-] Enlace descartado por falta de respuesta: {link}")
                continue

            titulo = limpiar_texto(getattr(entry, "title", "Sin título"))
            
            # Extracción del contenido descriptivo
            resumen_crudo = getattr(entry, "summary", "") or getattr(entry, "description", "")
            resumen = truncar_a_tres_lineas(limpiar_texto(resumen_crudo))

            fecha_formateada = (
                fecha_publicacion.strftime("%d/%m/%Y")
                if fecha_publicacion
                else "Publicación reciente"
            )

            entradas_validas.append({
                "titulo": titulo,
                "url": link,
                "fecha": fecha_formateada,
                "resumen": resumen,
            })

        if entradas_validas:
            articulos_recolectados[portal] = entradas_validas
            print(f"  [+] {len(entradas_validas)} artículo(s) válido(s) encontrado(s).")
        else:
            print("  [o] Sin publicaciones nuevas en la última semana.")

    return articulos_recolectados

# ---------------------------------------------------------------------------
# Generación de Correo y Envío
# ---------------------------------------------------------------------------
def construir_cuerpo_html(articulos_por_portal) -> str:
    """Construye el formato visual del correo listo para revisión."""
    html_out = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.5; color: #202124; background-color: #f8f9fa; padding: 20px;">
  <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border: 1px solid #dadce0; border-radius: 8px; padding: 24px;">
    <h2 style="color: #1a73e8; margin-top: 0;">Boletín Semanal: Innovación Educativa y STEM</h2>
    <p style="color: #5f6368; font-size: 14px;">
      Recopilación automatizada correspondiente a los últimos 7 días. Todos los enlaces han sido verificados de forma autónoma.
    </p>
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
"""
    if not articulos_por_portal:
        html_out += "<p style='color: #5f6368;'>No se detectaron nuevos artículos publicados durante los últimos 7 días en las fuentes monitoreadas.</p>"
    else:
        for portal, items in articulos_por_portal.items():
            html_out += f"""
            <div style="margin-bottom: 24px;">
              <h3 style="color: #137333; margin-bottom: 10px; border-bottom: 2px solid #ceead6; padding-bottom: 4px;">{portal}</h3>
              <ul style="padding-left: 20px; margin: 0;">
            """
            for it in items:
                html_out += f"""
                <li style="margin-bottom: 16px;">
                  <strong style="font-size: 15px;">
                    <a href="{it['url']}" target="_blank" style="color: #1a73e8; text-decoration: none;">{it['titulo']}</a>
                  </strong>
                  <br>
                  <span style="font-size: 12px; color: #70757a;">Fecha: {it['fecha']} | Enlace: {it['url']}</span>
                  <p style="margin: 6px 0 0 0; font-size: 13px; color: #3c4043;">
                    {it['resumen']}
                  </p>
                </li>
                """
            html_out += """
              </ul>
            </div>
            """

    html_out += """
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
    <p style="font-size: 11px; color: #80868b; margin-bottom: 0;">
      Enviado automáticamente por el agente de curaduría bibliográfica desde GitHub Actions.
    </p>
  </div>
</body>
</html>
"""
    return html_out

def enviar_reporte_correo(contenido_html: str):
    """Envía el boletín estructurado mediante SMTP SSL."""
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("Variables de entorno SMTP_USER o SMTP_PASS no definidas.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Boletín Semanal Verificado: Innovación Educativa y STEM"
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText(contenido_html, "html", "utf-8"))

    print(f"Conectando al servidor SMTP para enviar a {RECIPIENT_EMAIL}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
    print("Correo despachado exitosamente.")

# ---------------------------------------------------------------------------
# Entrada Principal
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Iniciando recopilación semanal de innovación educativa...")
    articulos = recopilar_articulos_semanales()
    cuerpo = construir_cuerpo_html(articulos)
    enviar_reporte_correo(cuerpo)
