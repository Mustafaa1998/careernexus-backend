import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_reset_email(to_email: str, reset_link: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    sender = os.getenv("SMTP_FROM", user).strip()

    if not host or not user or not password:
        raise RuntimeError("SMTP settings missing in .env (SMTP_HOST/SMTP_USER/SMTP_PASS).")

    subject = "CareerNexus Password Reset"
    body = f"""
Hello,

We received a request to reset your CareerNexus password.

Click this link to reset your password (valid for 15 minutes):
{reset_link}

If you did not request this, you can ignore this email.

Thanks,
CareerNexus Team
""".strip()

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(sender, to_email, msg.as_string())
