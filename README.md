# Voice-AI-

### Rakhsha AI - Women Safety Voice Emergency Trigger & SOS Dispatch Backend

An AI-powered emergency safety system that listens for the distress keyword **"Raksha"** and automatically verifies the registered speaker's vocal characteristics to prevent false alarms before dispatching SOS alerts to emergency guardians with live GPS coordinates.

---

## Features
- **Keyword Spotting (CNN)**: Detects when the user speaks or shouts the distress keyword *"Raksha"*.
- **Speaker Verification (SpeechBrain ECAPA-TDNN)**: Compares the audio embedding against the user's enrolled voice profile.
- **Emergency SOS Dispatch**: Automatically initiates emergency dispatch upon verified voice trigger.
- **Continuous Live Tracking**: Supports periodic GPS coordinate pings for live location tracking.
- **100% Free Notification Architecture**: Supports Console/Demo logging, Free Telegram Bot alerts, and Free Email alerts (SMTP).
- **Intelligent 60s Debounce**: Prevents spamming emergency guardians during rapid successive triggers.
- **Supabase Integration**: Stores user profiles, emergency contacts, incidents, and breadcrumbs.

---

## Quickstart

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/Scripts/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file and set your Supabase credentials:
```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_KEY="your-supabase-service-key"
```

### 3. Setup Database
Run `supabase_schema.sql` in your Supabase SQL Editor.

### 4. Run Server
```bash
uvicorn app.main:app --reload
```
Interactive API docs available at `http://127.0.0.1:8000/docs`.
