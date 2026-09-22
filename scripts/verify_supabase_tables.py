import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.supabase import supabase

tables = [
    "voice_profiles",
    "emergency_contacts",
    "sos_incidents",
    "incident_locations"
]

print("\n--- Checking Supabase tables status ---\n")

all_ok = True
for table in tables:
    try:
        res = supabase.table(table).select("*").limit(1).execute()
        print(f"  [OK] Table '{table}' exists and is accessible.")
    except Exception as e:
        all_ok = False
        print(f"  [MISSING] Table '{table}' not found in Supabase.")

print("\n" + "=" * 55)
if all_ok:
    print("SUCCESS: All Rakhsha AI tables are active in Supabase!")
else:
    print("ACTION NEEDED: Please run 'supabase_schema.sql' in your Supabase SQL Editor.")
print("=" * 55 + "\n")
