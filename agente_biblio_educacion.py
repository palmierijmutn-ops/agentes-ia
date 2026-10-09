import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai
from google.genai import types

# 1. Configuración de credenciales y parámetros
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SMTP_USER = os.environ.get("SMTP_USER")       # Tu cuenta de Gmail / correo emisor
SMTP_PASSWORD = os.environ.get("SMTP_PASS")   # Contraseña de aplicación (App Password)
RECIPIENT_EMAIL = "jpalmieri@frba.utn.edu.ar"

def generar_reporte_innovacion() -> str:
    """Consulta a Gemini con acceso a búsqueda web para compilar el boletín semanal."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = """
    Actúa como un agente de curaduría de contenidos en innovación educativa y educación STEM.
    
    Tarea:
    1. Busca artículos, informes y publicaciones recientes (de la última semana) de los principales
       portales y centros de referencia de América y Europa (ej. EdSurge, MIT Open Learning, Observatorio IFE,
       European Schoolnet, Educase, Scientix, etc.).
    2. Organiza los resultados por temáticas (ej. IA en el aula, Metodologías STEM, Política educativa, etc.).
    3. Para cada documento incluye:
       - Título:
       - URL:
       - Fecha de publicación:
       - Resumen (exactamente 3 renglones explicativos):
    4. Formatea la salida en HTML limpio, estructurado y legible para un correo electrónico.
    """

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    return response.text

def enviar_correo(html_content: str):
    """Envía el contenido generado por correo electrónico vía SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Boletín Semanal: Innovación Educativa y STEM (América y Europa)"
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT_EMAIL

    parte_html = MIMEText(html_content, "html")
    msg.attach(parte_html)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"Correo enviado exitosamente a {RECIPIENT_EMAIL}")

if __name__ == "__main__":
    print("Recopilando artículos y generando resumen...")
    reporte = generar_reporte_innovacion()
    print("Enviando correo...")
    enviar_correo(reporte)
