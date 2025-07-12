import os
import smtplib
from email.message import EmailMessage
import requests
from typing import Optional

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def test_smtp(host: str, port: int, user: str, pwd: str, use_tls: bool = True, timeout: int = 10) -> bool:
    """
    Attempt to connect and authenticate to an SMTP server.
    Returns True on success, False on any error.
    """
    try:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(user, pwd)
        server.quit()
        return True
    except Exception:
        return False

def test_proxy(proxy_str: str, timeout: int = 5) -> bool:
    """
    Test an HTTP/HTTPS proxy by fetching httpbin.org/ip.
    proxy_str formats accepted: ip:port or user:pass@ip:port
    """
    try:
        if '@' in proxy_str:
            creds, addr = proxy_str.split('@', 1)
            proxy_url = f"http://{creds}@{addr}"
        else:
            proxy_url = f"http://{proxy_str}"
        proxies = {"http": proxy_url, "https": proxy_url}
        resp = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False

def send_email(smtp_conf: dict, msg_conf: dict, proxy_conf: Optional[str] = None) -> bool:
    """
    Send a single email.

    smtp_conf keys: host, port, user, pwd, from_name, from_email, use_tls (bool)
    msg_conf keys: to (str), subject (str), body (str), attachments (list of file paths)
    proxy_conf: optional proxy string for outbound HTTP calls (not used by smtplib)
    """
    try:
        em = EmailMessage()
        em['From'] = f"{smtp_conf['from_name']} <{smtp_conf['from_email']}>"
        em['To'] = msg_conf['to']
        em['Subject'] = msg_conf['subject']
        em.set_content(msg_conf['body'], subtype='html')

        # Attach files if any
        for path in msg_conf.get('attachments', []):
            if os.path.isfile(path):
                with open(path, 'rb') as f:
                    data = f.read()
                maintype, subtype = 'application', 'octet-stream'
                filename = os.path.basename(path)
                em.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

        # Note: smtplib does not support proxies directly
        server = smtplib.SMTP(smtp_conf['host'], smtp_conf['port'], timeout=30)
        server.ehlo()
        if smtp_conf.get('use_tls', True):
            server.starttls()
            server.ehlo()
        server.login(smtp_conf['user'], smtp_conf['pwd'])
        server.send_message(em)
        server.quit()
        return True
    except Exception:
        return False
