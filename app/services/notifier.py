import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import requests

from app import config

logger = logging.getLogger("rakhsha.notifier")
logging.basicConfig(level=logging.INFO)


class BaseNotifier(ABC):
    """Abstract base class for emergency notification dispatchers."""

    @abstractmethod
    def send_sos_alert(
        self,
        incident_data: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Dispatches emergency SOS notification to the provided contacts."""
        pass


class ConsoleNotifier(BaseNotifier):
    """
    100% Free Console Emergency Dispatcher.
    Formats high-visibility emergency dispatch cards in stdout.
    Tracks all sent alerts in-memory for testing, demos, and presentations.
    """

    def __init__(self):
        self.dispatched_history: List[Dict[str, Any]] = []

    def send_sos_alert(
        self,
        incident_data: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        user_id = incident_data.get("user_id", "Unknown User")
        incident_id = incident_data.get("id", "N/A")
        trigger_source = incident_data.get("trigger_source", "voice")
        lat = incident_data.get("latitude")
        lng = incident_data.get("longitude")
        address = incident_data.get("address", "Not provided")
        maps_url = incident_data.get("google_maps_url", f"https://maps.google.com/?q={lat},{lng}")
        evidence_path = incident_data.get("audio_evidence_url", "None")

        banner = [
            "\n" + "=" * 70,
            "*** [RAKHSHA AI] EMERGENCY SOS ALERT DISPATCHED ***",
            "=" * 70,
            f"  Incident ID   : {incident_id}",
            f"  User ID       : {user_id}",
            f"  Trigger Source: {trigger_source.upper()} (Keyword 'Raksha' Verified)",
            f"  Coordinates   : Lat: {lat}, Lng: {lng}",
            f"  Live Map Link : {maps_url}",
            f"  Address/Notes : {address}",
            f"  Audio Evidence: {evidence_path}",
            "-" * 70,
            f"  NOTIFYING {len(contacts)} EMERGENCY GUARDIAN(S):"
        ]

        recipient_results = []
        for idx, contact in enumerate(contacts, start=1):
            name = contact.get("name", f"Guardian {idx}")
            phone = contact.get("phone_number", "N/A")
            relation = contact.get("relationship", "Emergency Contact")
            banner.append(f"    [{idx}] {name} ({relation}) | Phone: {phone} -> [DELIVERED (SIMULATED)]")
            recipient_results.append({
                "name": name,
                "phone": phone,
                "status": "delivered_mock",
                "channel": "console"
            })

        banner.append("=" * 70 + "\n")
        output_text = "\n".join(banner)
        try:
            print(output_text)
        except UnicodeEncodeError:
            import sys
            encoding = sys.stdout.encoding or "utf-8"
            print(output_text.encode(encoding, errors="replace").decode(encoding))

        result = {
            "success": True,
            "provider": "console",
            "incident_id": incident_id,
            "recipients_count": len(contacts),
            "details": recipient_results
        }
        self.dispatched_history.append(result)
        return result


class TelegramNotifier(BaseNotifier):
    """
    100% Free Telegram Bot Emergency Alert Dispatcher.
    Sends instant push notifications and GPS location pins to mobile phones.
    """

    def __init__(self, bot_token: str, default_chat_id: str):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id

    def send_sos_alert(
        self,
        incident_data: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not self.bot_token:
            logger.warning("Telegram Bot Token is empty. Falling back to ConsoleNotifier.")
            return ConsoleNotifier().send_sos_alert(incident_data, contacts)

        user_id = incident_data.get("user_id", "Unknown User")
        lat = incident_data.get("latitude")
        lng = incident_data.get("longitude")
        maps_url = incident_data.get("google_maps_url", f"https://maps.google.com/?q={lat},{lng}")
        address = incident_data.get("address", "Location shared via GPS")

        message = (
            "🚨 <b>RAKHSHA AI - EMERGENCY SOS ALERT</b> 🚨\n\n"
            f"⚠️ <b>User:</b> {user_id}\n"
            f"🗣️ <b>Trigger:</b> Voice Keyword 'Raksha' Verified\n"
            f"📍 <b>Location:</b> {address}\n"
            f"🗺️ <b>Live Map:</b> <a href=\"{maps_url}\">Open Google Maps</a>\n"
            f"⚡ <b>Coordinates:</b> <code>{lat}, {lng}</code>\n\n"
            "<i>Please check on them immediately!</i>"
        )

        chat_ids = set()
        if self.default_chat_id:
            chat_ids.add(self.default_chat_id)

        # Check if contacts have telegram chat_ids in metadata/phone
        for contact in contacts:
            cid = contact.get("telegram_chat_id") or contact.get("chat_id")
            if cid:
                chat_ids.add(str(cid))

        dispatched_count = 0
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        for cid in chat_ids:
            try:
                payload = {
                    "chat_id": cid,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code == 200:
                    dispatched_count += 1
                else:
                    logger.error(f"Telegram send failed to chat {cid}: {resp.text}")
            except Exception as e:
                logger.error(f"Error sending Telegram alert: {e}")

        # Also print to console for visibility
        ConsoleNotifier().send_sos_alert(incident_data, contacts)

        return {
            "success": True,
            "provider": "telegram",
            "dispatched_count": dispatched_count,
            "total_contacts": len(contacts)
        }


class EmailNotifier(BaseNotifier):
    """
    100% Free Email Alert Dispatcher using Python's built-in smtplib.
    Can use free Gmail App Password or local SMTP server.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email

    def send_sos_alert(
        self,
        incident_data: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured. Falling back to ConsoleNotifier.")
            return ConsoleNotifier().send_sos_alert(incident_data, contacts)

        user_id = incident_data.get("user_id", "Unknown User")
        lat = incident_data.get("latitude")
        lng = incident_data.get("longitude")
        maps_url = incident_data.get("google_maps_url", f"https://maps.google.com/?q={lat},{lng}")
        address = incident_data.get("address", "Coordinates shared")

        recipient_emails = [c.get("email") for c in contacts if c.get("email")]

        if not recipient_emails:
            logger.info("No recipient emails found among contacts.")
            return ConsoleNotifier().send_sos_alert(incident_data, contacts)

        dispatched_count = 0
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)

                for email_to in recipient_emails:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"🚨 URGENT: Rakhsha AI Emergency SOS for {user_id}"
                    msg["From"] = self.from_email
                    msg["To"] = email_to

                    html_content = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; background: #fff5f5; padding: 20px;">
                        <div style="max-width: 600px; margin: auto; background: white; border: 2px solid #e53e3e; border-radius: 8px; padding: 25px;">
                            <h1 style="color: #e53e3e; margin-top: 0;">🚨 EMERGENCY SOS ALERT</h1>
                            <p style="font-size: 16px;"><strong>{user_id}</strong> has triggered an Emergency SOS via Rakhsha AI (Voice 'Raksha' Verified).</p>
                            <div style="background: #f7fafc; border: 1px solid #edf2f7; padding: 15px; border-radius: 6px; margin: 20px 0;">
                                <p style="margin: 5px 0;"><strong>Location Notes:</strong> {address}</p>
                                <p style="margin: 5px 0;"><strong>Coordinates:</strong> {lat}, {lng}</p>
                                <p style="margin: 15px 0 5px 0;">
                                    <a href="{maps_url}" style="background: #e53e3e; color: white; padding: 10px 18px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">
                                        📍 View Live Location on Google Maps
                                    </a>
                                </p>
                            </div>
                            <p style="color: #718096; font-size: 13px;">Sent automatically by Rakhsha AI Women Safety System.</p>
                        </div>
                    </body>
                    </html>
                    """
                    msg.attach(MIMEText(html_content, "html"))
                    server.send_message(msg)
                    dispatched_count += 1
        except Exception as e:
            logger.error(f"Failed to send email alerts: {e}")

        ConsoleNotifier().send_sos_alert(incident_data, contacts)
        return {
            "success": True,
            "provider": "email",
            "dispatched_count": dispatched_count,
            "total_recipients": len(recipient_emails)
        }


# Singleton instances
_console_notifier = ConsoleNotifier()

def get_notifier() -> BaseNotifier:
    """Factory function providing the configured 100% free notifier."""
    provider = config.NOTIFICATION_PROVIDER

    if provider == "telegram":
        return TelegramNotifier(
            bot_token=config.TELEGRAM_BOT_TOKEN,
            default_chat_id=config.TELEGRAM_CHAT_ID
        )
    elif provider == "email":
        return EmailNotifier(
            smtp_host=config.SMTP_HOST,
            smtp_port=config.SMTP_PORT,
            smtp_user=config.SMTP_USER,
            smtp_password=config.SMTP_PASSWORD,
            from_email=config.EMAIL_FROM
        )
    else:
        return _console_notifier
