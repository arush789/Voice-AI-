import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import config
from app.services.notifier import get_notifier
from app.services.supabase import supabase

logger = logging.getLogger("rakhsha.sos_service")
logging.basicConfig(level=logging.INFO)

# In-memory fallbacks if Supabase tables have not been created yet
_fallback_contacts: Dict[str, List[Dict[str, Any]]] = {}
_fallback_incidents: Dict[str, Dict[str, Any]] = {}
_fallback_locations: Dict[str, List[Dict[str, Any]]] = {}

# Active incident tracker for debouncing: {user_id: {"incident_id": str, "timestamp": float}}
_active_user_incidents: Dict[str, Dict[str, Any]] = {}


def _get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ====================================================================
# EMERGENCY CONTACTS CRUD
# ====================================================================

def add_contact(
    user_id: str,
    name: str,
    phone_number: str,
    email: Optional[str] = None,
    relationship: str = "Emergency Contact",
    is_primary: bool = False
) -> Dict[str, Any]:
    contact_id = str(uuid.uuid4())
    contact_data = {
        "id": contact_id,
        "user_id": user_id,
        "name": name,
        "phone_number": phone_number,
        "email": email or "",
        "relationship": relationship,
        "is_primary": is_primary,
        "created_at": _get_utc_now(),
        "updated_at": _get_utc_now()
    }

    try:
        res = supabase.table("emergency_contacts").insert(contact_data).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        logger.warning(f"Supabase emergency_contacts insert failed ({e}). Using local fallback.")

    if user_id not in _fallback_contacts:
        _fallback_contacts[user_id] = []
    _fallback_contacts[user_id].append(contact_data)
    return contact_data


def get_contacts(user_id: str) -> List[Dict[str, Any]]:
    try:
        res = supabase.table("emergency_contacts").select("*").eq("user_id", user_id).execute()
        if res.data is not None and len(res.data) > 0:
            return res.data
    except Exception as e:
        logger.warning(f"Supabase emergency_contacts select failed ({e}). Checking local fallback.")

    return _fallback_contacts.get(user_id, [])


def delete_contact(contact_id: str) -> bool:
    try:
        supabase.table("emergency_contacts").delete().eq("id", contact_id).execute()
    except Exception as e:
        logger.warning(f"Supabase emergency_contacts delete failed ({e}).")

    for uid, contacts in _fallback_contacts.items():
        _fallback_contacts[uid] = [c for c in contacts if c.get("id") != contact_id]
    return True


# ====================================================================
# SOS TRIGGER & INCIDENT LIFECYCLE
# ====================================================================

def trigger_sos(
    user_id: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    address: Optional[str] = None,
    trigger_source: str = "voice",
    audio_file_path: Optional[str] = None,
    keyword_score: Optional[float] = None,
    speaker_similarity: Optional[float] = None,
    custom_contacts: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main SOS trigger logic:
    1. Checks 60-second debounce window to prevent duplicate alerts.
    2. Generates Google Maps tracking link.
    3. Saves emergency voice audio clip as evidence.
    4. Dispatches emergency alerts to guardians via configured Notifier.
    5. Persists incident and location trace.
    """
    current_time = time.time()
    now_iso = _get_utc_now()

    # 1. Debounce check: group rapid successive triggers into existing active incident
    if user_id in _active_user_incidents:
        last_info = _active_user_incidents[user_id]
        elapsed = current_time - last_info["timestamp"]
        if elapsed < config.DEBOUNCE_SECONDS:
            logger.info(f"SOS triggered within debounce window ({elapsed:.1f}s < {config.DEBOUNCE_SECONDS}s). Updating existing incident.")
            existing_id = last_info["incident_id"]

            if latitude is not None and longitude is not None:
                update_incident_location(existing_id, latitude, longitude, address)

            return {
                "success": True,
                "incident_id": existing_id,
                "status": "active",
                "debounced": True,
                "message": f"Successive trigger grouped into active incident {existing_id}.",
                "alert_dispatched": False
            }

    # 2. Build Google Maps URL if coordinates provided
    maps_url = ""
    if latitude is not None and longitude is not None:
        maps_url = f"https://maps.google.com/?q={latitude},{longitude}"

    incident_id = str(uuid.uuid4())

    # 3. Preserve emergency audio evidence
    evidence_path = ""
    if audio_file_path and os.path.exists(audio_file_path):
        os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
        evidence_ext = os.path.splitext(audio_file_path)[1] or ".wav"
        target_evidence_path = os.path.join(config.EVIDENCE_DIR, f"{incident_id}{evidence_ext}")
        try:
            shutil.copy(audio_file_path, target_evidence_path)
            evidence_path = target_evidence_path
            logger.info(f"Preserved emergency audio evidence at: {evidence_path}")
        except Exception as e:
            logger.error(f"Failed to copy emergency audio evidence: {e}")

    # 4. Resolve Emergency Contacts
    contacts = custom_contacts or get_contacts(user_id)
    if not contacts:
        # Fallback default guardian contact for college presentation demo
        contacts = [{
            "id": "demo_guardian",
            "name": "Guardian (Demo)",
            "phone_number": "+919999999999",
            "email": "guardian.demo@example.com",
            "relationship": "Emergency Contact",
            "is_primary": True
        }]

    # 5. Incident Record
    incident_data = {
        "id": incident_id,
        "user_id": user_id,
        "status": "active",
        "trigger_source": trigger_source,
        "latitude": latitude,
        "longitude": longitude,
        "address": address or "GPS Location Available",
        "google_maps_url": maps_url,
        "audio_evidence_url": evidence_path,
        "keyword_score": keyword_score,
        "speaker_similarity": speaker_similarity,
        "alert_dispatched": True,
        "dispatched_contacts_count": len(contacts),
        "created_at": now_iso,
        "resolved_at": None,
        "resolution_note": None
    }

    # 6. Dispatch Emergency Notification
    notifier = get_notifier()
    dispatch_result = notifier.send_sos_alert(incident_data, contacts)

    # 7. Persist to Supabase (or fallback)
    try:
        supabase.table("sos_incidents").insert(incident_data).execute()
    except Exception as e:
        logger.warning(f"Supabase sos_incidents insert failed ({e}). Using local fallback store.")

    _fallback_incidents[incident_id] = incident_data

    # 8. Record initial location breadcrumb
    if latitude is not None and longitude is not None:
        location_crumb = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "latitude": latitude,
            "longitude": longitude,
            "address": address or "",
            "recorded_at": now_iso
        }
        try:
            supabase.table("incident_locations").insert(location_crumb).execute()
        except Exception as e:
            logger.warning(f"Supabase incident_locations insert failed ({e}).")

        if incident_id not in _fallback_locations:
            _fallback_locations[incident_id] = []
        _fallback_locations[incident_id].append(location_crumb)

    # 9. Set active incident for debounce tracking
    _active_user_incidents[user_id] = {
        "incident_id": incident_id,
        "timestamp": current_time
    }

    return {
        "success": True,
        "incident_id": incident_id,
        "status": "active",
        "debounced": False,
        "google_maps_url": maps_url,
        "audio_evidence_url": evidence_path,
        "contacts_notified": len(contacts),
        "notification_provider": dispatch_result.get("provider", "console"),
        "created_at": now_iso
    }


def update_incident_location(
    incident_id: str,
    latitude: float,
    longitude: float,
    address: Optional[str] = None
) -> Dict[str, Any]:
    """Updates live GPS tracking coordinates for an ongoing incident."""
    now_iso = _get_utc_now()
    maps_url = f"https://maps.google.com/?q={latitude},{longitude}"

    location_crumb = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "latitude": latitude,
        "longitude": longitude,
        "address": address or "",
        "recorded_at": now_iso
    }

    # Append to incident locations
    try:
        supabase.table("incident_locations").insert(location_crumb).execute()
    except Exception as e:
        logger.warning(f"Supabase incident_locations insert failed: {e}")

    if incident_id not in _fallback_locations:
        _fallback_locations[incident_id] = []
    _fallback_locations[incident_id].append(location_crumb)

    # Update latest coordinates on incident
    update_fields = {
        "latitude": latitude,
        "longitude": longitude,
        "google_maps_url": maps_url
    }
    if address:
        update_fields["address"] = address

    try:
        supabase.table("sos_incidents").update(update_fields).eq("id", incident_id).execute()
    except Exception as e:
        logger.warning(f"Supabase sos_incidents update failed: {e}")

    if incident_id in _fallback_incidents:
        _fallback_incidents[incident_id].update(update_fields)

    return {
        "success": True,
        "incident_id": incident_id,
        "latitude": latitude,
        "longitude": longitude,
        "google_maps_url": maps_url,
        "updated_at": now_iso
    }


def resolve_incident(
    incident_id: str,
    resolution_note: str = "Resolved by user"
) -> Dict[str, Any]:
    """Closes an active emergency incident."""
    now_iso = _get_utc_now()

    update_payload = {
        "status": "resolved",
        "resolved_at": now_iso,
        "resolution_note": resolution_note
    }

    try:
        supabase.table("sos_incidents").update(update_payload).eq("id", incident_id).execute()
    except Exception as e:
        logger.warning(f"Supabase sos_incidents resolve failed: {e}")

    if incident_id in _fallback_incidents:
        _fallback_incidents[incident_id].update(update_payload)
        user_id = _fallback_incidents[incident_id].get("user_id")
        if user_id in _active_user_incidents and _active_user_incidents[user_id].get("incident_id") == incident_id:
            del _active_user_incidents[user_id]

    return {
        "success": True,
        "incident_id": incident_id,
        "status": "resolved",
        "resolved_at": now_iso
    }


def get_user_incidents(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all historical incidents for a user."""
    try:
        res = supabase.table("sos_incidents").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        if res.data is not None:
            return res.data
    except Exception as e:
        logger.warning(f"Supabase sos_incidents select failed: {e}")

    incidents = [inc for inc in _fallback_incidents.values() if inc.get("user_id") == user_id]
    return sorted(incidents, key=lambda x: x.get("created_at", ""), reverse=True)


def get_incident_details(incident_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves comprehensive details of a specific incident including breadcrumb trail."""
    incident = None
    try:
        res = supabase.table("sos_incidents").select("*").eq("id", incident_id).execute()
        if res.data:
            incident = res.data[0]
    except Exception:
        pass

    if not incident:
        incident = _fallback_incidents.get(incident_id)

    if not incident:
        return None

    # Fetch locations
    locations = []
    try:
        loc_res = supabase.table("incident_locations").select("*").eq("incident_id", incident_id).order("recorded_at").execute()
        if loc_res.data:
            locations = loc_res.data
    except Exception:
        pass

    if not locations:
        locations = _fallback_locations.get(incident_id, [])

    incident_copy = dict(incident)
    incident_copy["location_history"] = locations
    return incident_copy
