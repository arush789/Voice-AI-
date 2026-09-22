import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

# ML Model Paths & Hardware
DEVICE = os.getenv("DEVICE", "cuda:0" if os.getenv("USE_CUDA", "true").lower() == "true" else "cpu")
KEYWORD_MODEL_PATH = os.getenv("KEYWORD_MODEL_PATH", str(BASE_DIR / "models" / "rakhsha_keyword_cnn.pt"))
SPEAKER_MODEL_SOURCE = os.getenv("SPEAKER_MODEL_SOURCE", "speechbrain/spkrec-ecapa-voxceleb")
PROFILE_DIR = os.getenv("PROFILE_DIR", str(BASE_DIR / "models" / "user_voice_profiles"))

# Audio Preprocessing Specs
TARGET_SAMPLE_RATE = 16000
TARGET_FRAMES = 200
N_MELS = 80
N_FFT = 512
HOP_LENGTH = 160

# Model Detection Thresholds
KEYWORD_THRESHOLD = float(os.getenv("KEYWORD_THRESHOLD", "0.50"))
SPEAKER_THRESHOLD = float(os.getenv("SPEAKER_THRESHOLD", "0.3887"))

# Emergency SOS & Debounce Settings
DEBOUNCE_SECONDS = int(os.getenv("DEBOUNCE_SECONDS", "60"))
EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", str(BASE_DIR / "evidence" / "audio"))

# 100% Free Notification Dispatch Settings
# Options: "console" (default, free demo), "telegram" (free bot), "email" (free SMTP/Gmail)
NOTIFICATION_PROVIDER = os.getenv("NOTIFICATION_PROVIDER", "console").strip().lower()

# Free Telegram Bot Configuration (Optional, 100% free)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Free Email / SMTP Configuration (Optional, e.g. free Gmail App Password)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "").strip() or SMTP_USER
