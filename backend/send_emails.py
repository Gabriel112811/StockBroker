import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from jinja2 import Environment, FileSystemLoader

import json

url = "https://stockbroker.ddns.net"

path = "keys.json" if os.path.exists("keys.json") else "backend/keys.json"


with open(path, 'r') as f:
    daten = json.load(f)
    SENDER_EMAIL, SENDER_PASSWORD = daten['address'], daten['gmail_app_password']

# Konfiguration - Sichere Speicherung von Zugangsdaten!
# Verwende Umgebungsvariablen oder eine Konfigurationsdatei anstelle von Hardcoding.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # Für TLS
EMAIL_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails')

# Jinja2-Umgebung einrichten
env = Environment(loader=FileSystemLoader(EMAIL_TEMPLATES_DIR))


def _send_email(receiver_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """
    Interne Funktion zum Versenden einer E-Mail.
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print(
            "Fehler: Absender-E-Mail oder Passwort nicht konfiguriert (Umgebungsvariablen GMAIL_USER, GMAIL_APP_PASSWORD).")
        return False

    message = MIMEMultipart("alternative")
    message["From"] = SENDER_EMAIL
    message["To"] = receiver_email
    message["Subject"] = Header(subject, "utf-8").encode()  # Für Umlaute im Betreff

    # Füge den reinen Textteil hinzu (wichtig für Spam-Filter und E-Mail-Clients ohne HTML)
    if text_content:
        message.attach(MIMEText(text_content, "plain", "utf-8"))
    else:
        # Fallback: Erzeuge Text aus HTML (sehr rudimentär, besser expliziten Text bereitstellen)
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = True
        text_from_html = h.handle(html_content)
        message.attach(MIMEText(text_from_html, "plain", "utf-8"))

    # Füge den HTML-Teil hinzu
    message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # TLS-Verschlüsselung aktivieren
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, message.as_string())
        print(f"E-Mail erfolgreich an {receiver_email} gesendet.")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"Fehler bei der Authentifizierung mit dem Gmail-Server. Überprüfe E-Mail und App-Passwort.")
        return False
    except Exception as e:
        print(f"Fehler beim Senden der E-Mail an {receiver_email}: {e}")
        return False


def send_welcome_email(recipient_email: str, user_name: str, activation_token: str,
                       base_url: str = "https://deineapp.com/activate") -> bool:
    """
    Versendet eine Willkommens-E-Mail.
    """
    subject = f"Willkommen bei Unserem Service, {user_name}!"
    template = env.get_template("welcome_email.html")
    activation_link = f"{base_url}?token={activation_token}"

    # Erzeuge Plain-Text-Alternative
    text_content = f"""Hallo {user_name},

Willkommen bei unserem Service! Wir freuen uns, dich an Bord zu haben.

Bitte klicke auf den folgenden Link, um dein Konto zu aktivieren (oder kopiere ihn in deinen Browser):
{activation_link}

Dein Aktivierungs-Token (falls der Link nicht funktioniert): {activation_token}

Viele Grüße,
Dein Team
"""
    html_content = template.render(user_name=user_name, token=activation_token, activation_link=activation_link)
    return _send_email(recipient_email, subject, html_content, text_content)


def send_confirmation_email(recipient_email: str, user_name: str, confirmation_code: str) -> bool:
    """
    Versendet eine E-Mail zur Bestätigung der E-Mail-Adresse mit einem Code.
    """
    subject = "Bestätige deine E-Mail-Adresse"
    template = env.get_template("confirm_email.html")

    text_content = f"""Hallo {user_name},

Bitte verwende den folgenden Code, um deine E-Mail-Adresse zu bestätigen:
{confirmation_code}

Dieser Code ist für 10 Minuten gültig.

Viele Grüße,
Dein Team
"""
    html_content = template.render(user_name=user_name, code=confirmation_code)
    return _send_email(recipient_email, subject, html_content, text_content)


def send_password_reset_email(recipient_email: str, user_name: str, reset_code: str):
    """
    Versendet eine E-Mail zum Zurücksetzen des Passworts mit einem Code.
    """
    subject = "Anfrage zum Zurücksetzen deines Passworts"
    template = env.get_template("password_reset_email.html")

    text_content = f"""Hallo {user_name},

Du hast eine Anfrage zum Zurücksetzen deines Passworts gestellt. Bitte verwende den folgenden Code, um dein Passwort zurückzusetzen:
{reset_code}

Dieser Code ist für 10 Minuten gültig. Wenn du diese Anfrage nicht gestellt hast, ignoriere bitte diese E-Mail.

Viele Grüße,
Dein Team
"""
    html_content = template.render(user_name=user_name, code=reset_code)
    return _send_email(recipient_email, subject, html_content, text_content)


# --- Beispielaufrufe (zum Testen) ---
if __name__ == "__main__":
    import os

    test_recipient = "fanvielerdinge@gmail.com"  # Ersetze dies durch eine echte Test-E-Mail-Adresse

    print(f"Stelle sicher, dass die Umgebungsvariablen GMAIL_USER und GMAIL_APP_PASSWORD gesetzt sind.")
    print(f"Verwendeter SENDER_EMAIL: {SENDER_EMAIL}")

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Bitte setze die Umgebungsvariablen GMAIL_USER und GMAIL_APP_PASSWORD, bevor du das Skript ausführst.")
    else:
        print("\nSende Willkommens-E-Mail...")
        welcome_success = send_welcome_email(
            recipient_email=test_recipient,
            user_name="Max Mustermann",
            activation_token="abcdef123456token",
            base_url="https://example.com/activate"  # Anpassen an deine App
        )
        print(f"Willkommens-E-Mail gesendet: {welcome_success}")

        print("\nSende Bestätigungs-E-Mail...")
        confirm_success = send_confirmation_email(
            recipient_email=test_recipient,
            user_name="Max Mustermann",
            confirmation_code="123456"
        )
        print(f"Bestätigungs-E-Mail gesendet: {confirm_success}")

        print("\nSende Passwort-Zurücksetzen-E-Mail...")
        reset_success = send_password_reset_email(
            recipient_email=test_recipient,
            user_name="Max Mustermann",
            reset_code="654321"
        )
        print(f"Passwort-Zurücksetzen-E-Mail gesendet: {reset_success}")