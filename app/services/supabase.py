import os

from dotenv import load_dotenv
from supabase import create_client, Client


# Load variables from .env
load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not set")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY is not set")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)