"""
Odesilani e-mailu (napr. reset hesla) pres SMTP.
Konfigurace se bere z promennych prostredi - nastav je na serveru (napr. v .env
nebo v konfiguraci WSGI aplikace na PythonAnywhere):

  SMTP_HOST      - napr. smtp.gmail.com
  SMTP_PORT      - napr. 587
  SMTP_USER      - prihlasovaci jmeno k SMTP uctu (casto cela e-mailova adresa)
  SMTP_PASSWORD  - heslo / app-password k tomu uctu
  SMTP_FROM      - adresa, ktera se zobrazi jako odesilatel (napr. Piply <noreply@piply.com>)

Pokud tyhle promenne nejsou nastavene, e-mail se neposle, ale appka nespadne -
misto toho se obsah e-mailu jen vypise do serverovyho logu, aby slo v klidu
vyvijet/testovat i bez skutecne nakonfigurovaneho SMTP.
"""

import os
import smtplib
from email.mime.text import MIMEText


def send_email(to_email, subject, body):
    host = os.environ.get("SMTP_HOST", "").strip()
    port = os.environ.get("SMTP_PORT", "587").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM", "").strip() or user

    if not host or not user or not password:
        print(f"[EMAIL NENÍ NAKONFIGUROVÁN – jen simulace] Komu: {to_email}\nPředmět: {subject}\n\n{body}")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, int(port), timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[CHYBA PŘI ODESÍLÁNÍ E-MAILU] {e}")
        return False
