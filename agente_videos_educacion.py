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

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MARCADOR_INICIO = "<!-- INICIO_CONTENIDO_DINAMICO -->"
MARCADOR_FIN = "<!-- FIN_CONTENIDO_DINAMICO -->"

# ---------------------------------------------------------------------------
# Directorio de Canales de YouTube (11 Canales Oficiales)
# ---------------------------------------------------------------------------
CANALES_YOUTUBE_EDUCACION = {
    # Referencia principal
    "Aprendemos Juntos 2030 (BBVA)": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCI6QcXatPEq23msvPCEBGwg",
        "idioma": "Español",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    },
    # Eje 1: Conferencias Breves y Pensadores Globales
    "TED (Oficial)": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCAuUUnT6oDeKwE6v1NGQxug",
        "idioma": "Inglés",
        "categoria": "Conferencias Breves y Charlas Inspiradoras"
    },
    "TED en Español": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsh2_vYw_lR9k1k9wL1m3Yg",
        "idioma": "Español",
        "categoria": "Conferencias Breves y Charlas Inspiradoras"
    },
    "Big Think": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCvQECJukTDE2i6aCoMnS-Vg",
        "idioma": "Inglés",
        "categoria": "Conferencias Breves y Charlas Inspiradoras"
    },
    "Talks at Google": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCtXKDgv1AVoG88PLl8nGXmw",
        "idioma": "Inglés",
        "categoria": "Conferencias Breves y Charlas Inspiradoras"
    },
    "The Royal Institution": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCYeF244yNGuCeGT83047gFw",
        "idioma": "Inglés",
        "categoria": "Conferencias Breves y Charlas Inspiradoras"
    },
    # Eje 2: Entrevistas en Profundidad, Psicología, Neurociencia y Humanismo
    "Espacio Fundación Telefónica": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC6z83n8k_9q_6X1zHhG44Xw",
        "idioma": "Español",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    },
    "Huberman Lab": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC2D2CMWXMOVWx7giW1n3LIg",
        "idioma": "Inglés",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    },
    "Casa de América (Diálogos y Humanismo)": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCZl_uB94yV-u7wB2yA0mGmA",
        "idioma": "Español",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    },
    "On Being with Krista Tippett": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCrJ5Y6zZ94l6iGz5pYfC4Ow",
        "idioma": "Inglés",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    },
    "Entiende Tu Mente": {
        "feed_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC2sYnE5l8uWvHwY3yX5Z6ZQ",
        "idioma": "Español",
        "categoria": "Entrevistas en Profundidad y Humanismo"
    }
}

# ---------------------------------------------------------------------------
# Funciones Auxiliares
# ---------------------------------------------------------------------------
def limpiar_texto(html_text: str) -> str:
    if not html_text:
        return "Sin descripción disponible."
    texto = re.sub(r"<[^>]+>", " ", html_text)
    texto = html.unescape(texto)
    return " ".join(texto.split())

def truncar_a_tres_lineas(texto: str, max_palabras: int = 40) -> str:
    palabras = texto.split()
    if len(palabras) > max_palabras:
        return " ".join(palabras[:max_palabras]) + "..."
    return texto

def es_enlace_valido(url: str, timeout: int = 8) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        req = urllib.request.Request(url, headers=HEADERS_NAVEGADOR, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 301, 302)
    except Exception:
        pass

    try:
        req = urllib.request.Request(url, headers=HEADERS_NAVEGADOR, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def obtener_fecha_entrada(entry) -> datetime | None:
    tiempo_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tiempo_struct:
        try:
            return datetime.fromtimestamp(time.mktime(tiempo_struct), tz=timezone.utc)
        except Exception:
            return None
    return None

# ---------------------------------------------------------------------------
# Cosecha y Filtrado
# ---------------------------------------------------------------------------
def recolectar_videos_semanales():
    ahora_utc = datetime.now(timezone.utc)
    limite_semanal = ahora_utc - timedelta(days=7)
    videos_por_canal = {}

    for nombre_canal, info in CANALES_YOUTUBE_EDUCACION.items():
        print(f"Consultando: {nombre_canal}...")
        try:
            parsed = feedparser.parse(info["feed_url"], request_headers=HEADERS_NAVEGADOR)
        except Exception as e:
            print(f"  [!] Error al leer canal {nombre_canal}: {e}")
            continue

        videos_validos = []
        for entry in parsed.entries:
            fecha_pub = obtener_fecha_entrada(entry)
            if fecha_pub and fecha_pub < limite_semanal:
                continue

            link = getattr(entry, "link", None)
            if not link or not es_enlace_valido(link):
                continue

            titulo = limpiar_texto(getattr(entry, "title", "Sin título"))
            desc_cruda = getattr(entry, "summary", "") or getattr(entry, "description", "")
            resumen = truncar_a_tres_lineas(limpiar_texto(desc_cruda))
            fecha_str = fecha_pub.strftime("%d/%m/%Y") if fecha_pub else "Reciente"

            videos_validos.append({
                "titulo": titulo,
                "url": link,
                "fecha": fecha_str,
                "resumen": resumen,
                "idioma": info["idioma"],
                "categoria": info["categoria"]
            })

        if videos_validos:
            videos_por_canal[nombre_canal] = videos_validos
            print(f"  [+] {len(videos_validos)} video(s) reciente(s).")
        else:
            print("  [o] Sin publicaciones recientes.")

    return videos_por_canal

# ---------------------------------------------------------------------------
# Generación Web para GitHub Pages (docs/videos/index.html)
# ---------------------------------------------------------------------------
def generar_fragmento_videos_html(videos_por_canal) -> str:
    fecha_actual = datetime.now().strftime("%d/%m/%Y")

    if not videos_por_canal:
        return f"""
        <div class="referencia-seccion" style="background-color: #f8f9fa; border-left: 4px solid var(--accent); padding: 14px 18px; margin-bottom: 24px; border-radius: 0 4px 4px 0;">
          <p style="margin: 0; font-size: 0.95rem; color: #3c4043;">
            <strong>Curaduría Audiovisual Semanal</strong><br>
            <span style="font-size: 0.85rem; color: var(--text-muted);">
              Corte al {fecha_actual} | Relevamiento de conferencias y charlas en los últimos 7 días.
            </span>
          </p>
          <p style="margin: 8px 0 0 0; font-size: 0.9rem; color: #5f6368; font-style: italic;">
            No se detectaron nuevos videos publicados durante los últimos 7 días en los canales monitoreados.
          </p>
        </div>
        """

    fragmento = f"""
    <div class="referencia-seccion" style="background-color: #f8f9fa; border-left: 4px solid var(--accent); padding: 14px 18px; margin-bottom: 24px; border-radius: 0 4px 4px 0;">
      <p style="margin: 0; font-size: 0.95rem; color: #202124;">
        <strong>Curaduría Audiovisual Semanal: Pensamiento, Ciencia y Educación</strong>
      </p>
      <p style="margin: 4px 0 0 0; font-size: 0.85rem; color: #5f6368; line-height: 1.4;">
        Selección de conferencias breves, diálogos y entrevistas de referencia cosechados durante los últimos 7 días (actualizado al <strong>{fecha_actual}</strong>). Enlaces oficiales de YouTube verificados.
      </p>
    </div>
    """

    for canal, items in videos_por_canal.items():
        cat = items[0]["categoria"]
        lang = items[0]["idioma"]
        fragmento += f"""
        <div class='portal-section'>
          <h3 class='portal-title'>
            {canal} <span style='font-size: 12px; font-weight: normal; color: #5f6368;'>({cat} - {lang})</span>
          </h3>
          <ul style='padding-left: 20px; margin: 0;'>
        """
        for it in items:
            fragmento += f"""
            <li class='item-block'>
              <a href="{it['url']}" target="_blank" class='item-title' style='color: #c5221f;'>▶ {it['titulo']}</a><br>
              <span class='item-meta'>Publicado: {it['fecha']} | Canal oficial</span>
              <p class='item-summary'>{it['resumen']}</p>
            </li>
            """
        fragmento += "</ul></div>"

    return fragmento

def actualizar_pagina_videos(fragmento_html: str):
    os.makedirs("docs/videos", exist_ok=True)
    plantilla_path = "docs/template_videos.html"
    salida_path = "docs/videos/index.html"

    archivo_base = plantilla_path if os.path.exists(plantilla_path) else salida_path
    if not os.path.exists(archivo_base):
        raise FileNotFoundError(f"No se encontró la plantilla en {archivo_base}")

    with open(archivo_base, "r", encoding="utf-8") as f:
        plantilla = f.read()

    patron = rf"({re.escape(MARCADOR_INICIO)})(.*?)({re.escape(MARCADOR_FIN)})"
    nuevo_bloque = rf"\1\n{fragmento_html}\n\3"
    html_final = re.sub(patron, nuevo_bloque, plantilla, flags=re.DOTALL)

    with open(salida_path, "w", encoding="utf-8") as f:
        f.write(html_final)
    print(f"[+] '{salida_path}' actualizado exitosamente.")

# ---------------------------------------------------------------------------
# Correo Electrónico
# ---------------------------------------------------------------------------
def construir_cuerpo_correo(videos_por_canal) -> str:
    html_out = """<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #202124; background-color: #f8f9fa; padding: 20px;">
  <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border: 1px solid #dadce0; border-radius: 8px; padding: 24px;">
    <h2 style="color: #c5221f; margin-top: 0;">Boletín Semanal: Conferencias y Videos Educativos</h2>
    <p style="color: #5f6368; font-size: 14px;">Selección semanal de videos y conferencias de referencia (CIIE - UTN FRBA).</p>
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
"""
    if not videos_por_canal:
        html_out += "<p style='color: #5f6368;'>No se detectaron videos nuevos esta semana.</p>"
    else:
        for canal, items in videos_por_canal.items():
            html_out += f"<h3 style='color: #202124; margin-bottom: 4px;'>{canal}</h3><ul style='padding-left: 20px;'>"
            for it in items:
                html_out += f"""
                <li style='margin-bottom: 12px;'>
                  <strong><a href='{it['url']}' target='_blank' style='color: #c5221f;'>▶ {it['titulo']}</a></strong><br>
                  <span style='font-size: 12px; color: #70757a;'>Fecha: {it['fecha']}</span>
                  <p style='margin: 4px 0 0 0; font-size: 13px; color: #3c4043;'>{it['resumen']}</p>
                </li>
                """
            html_out += "</ul>"
    html_out += """
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
    <p style="font-size: 11px; color: #80868b; margin-bottom: 0;">CIIE - UTN FRBA | Enviado automáticamente desde GitHub Actions.</p>
  </div>
</body></html>"""
    return html_out

def enviar_reporte_correo(contenido_html: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("Variables SMTP_USER o SMTP_PASS no definidas.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Boletín Semanal de Videos: Pensamiento, Ciencia y Educación"
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(contenido_html, "html", "utf-8"))

    print(f"Enviando correo a {RECIPIENT_EMAIL}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
    print("Correo enviado exitosamente.")

# ---------------------------------------------------------------------------
# Ejecución Principal
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Iniciando recopilación semanal de conferencias y videos...")
    videos = recolectar_videos_semanales()
    
    # 1. Actualiza la página web en GitHub Pages (docs/videos/index.html)
    fragmento = generar_fragmento_videos_html(videos)
    actualizar_pagina_videos(fragmento)

    # 2. Envía el boletín por correo electrónico
    cuerpo = construir_cuerpo_correo(videos)
    enviar_reporte_correo(cuerpo)
