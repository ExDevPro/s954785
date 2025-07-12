# engine/smtp_worker.py

import smtplib
import socket
from typing import Dict

def test_smtp(smtp_data: Dict) -> Dict:
    result = {"status": "Fail", "message": ""}

    host = smtp_data.get("Host", "").strip()
    port = int(smtp_data.get("Port", 0))
    user = smtp_data.get("User", "").strip()
    password = smtp_data.get("Password", "").strip()
    security = smtp_data.get("Security", "None").strip().upper()

    try:
        if security == "SSL":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if security in ["TLS", "STARTTLS"]:
                server.starttls()

        server.login(user, password)
        server.quit()

        result["status"] = "Success"
        result["message"] = "Login successful"
    except smtplib.SMTPAuthenticationError:
        result["message"] = "Authentication failed"
    except (smtplib.SMTPException, socket.error) as e:
        result["message"] = str(e)
    except Exception as e:
        result["message"] = f"Unhandled error: {str(e)}"

    return result
