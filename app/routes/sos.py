from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.services import sos_service

router = APIRouter(
    prefix="/sos",
    tags=["SOS Emergency Dispatch"]
)


# ====================================================================
# PYDANTIC SCHEMAS
# ====================================================================

class ContactCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID associated with contact")
    name: str = Field(..., description="Full name of emergency contact")
    phone_number: str = Field(..., description="Phone number with country code")
    email: Optional[str] = Field(None, description="Optional email address")
    relationship: Optional[str] = Field("Guardian", description="Relationship (e.g., Mother, Father, Friend)")
    is_primary: Optional[bool] = Field(False, description="Primary contact flag")


class SOSTriggerRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user in emergency")
    latitude: Optional[float] = Field(None, description="Current GPS latitude")
    longitude: Optional[float] = Field(None, description="Current GPS longitude")
    address: Optional[str] = Field(None, description="Current street/area address or landmark")
    trigger_source: Optional[str] = Field("manual", description="Source of trigger: 'manual', 'voice', or 'sensor'")
    custom_contacts: Optional[List[Dict[str, Any]]] = Field(None, description="Optional contact list overriding DB")


class LocationUpdateRequest(BaseModel):
    latitude: float = Field(..., description="Updated GPS latitude")
    longitude: float = Field(..., description="Updated GPS longitude")
    address: Optional[str] = Field(None, description="Updated street/area address")


class IncidentResolveRequest(BaseModel):
    resolution_note: Optional[str] = Field("Resolved by user", description="Reason or note for closing the incident")


# ====================================================================
# EMERGENCY CONTACT ENDPOINTS
# ====================================================================

@router.post("/contacts", status_code=201)
async def create_contact(payload: ContactCreateRequest):
    """Registers a new emergency guardian contact for a user."""
    if not payload.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not payload.phone_number.strip():
        raise HTTPException(status_code=400, detail="phone_number is required")

    contact = sos_service.add_contact(
        user_id=payload.user_id.strip(),
        name=payload.name.strip(),
        phone_number=payload.phone_number.strip(),
        email=payload.email.strip() if payload.email else None,
        relationship=payload.relationship or "Guardian",
        is_primary=payload.is_primary or False
    )
    return {
        "success": True,
        "message": "Emergency contact added successfully",
        "contact": contact
    }


@router.get("/contacts/{user_id}")
async def list_contacts(user_id: str = Path(..., description="User ID")):
    """Retrieves all registered emergency contacts for a given user."""
    contacts = sos_service.get_contacts(user_id.strip())
    return {
        "success": True,
        "user_id": user_id,
        "contacts_count": len(contacts),
        "contacts": contacts
    }


@router.delete("/contacts/{contact_id}")
async def remove_contact(contact_id: str = Path(..., description="Contact ID to delete")):
    """Deletes an emergency contact."""
    sos_service.delete_contact(contact_id)
    return {
        "success": True,
        "message": f"Contact {contact_id} removed"
    }


# ====================================================================
# SOS TRIGGER & INCIDENT MANAGEMENT ENDPOINTS
# ====================================================================

@router.post("/trigger")
async def trigger_emergency_sos(payload: SOSTriggerRequest):
    """
    Manually triggers an SOS emergency alert (panic button press or external trigger).
    Generates a live tracking link and dispatches alerts to the user's emergency contacts.
    """
    if not payload.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    result = sos_service.trigger_sos(
        user_id=payload.user_id.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address,
        trigger_source=payload.trigger_source or "manual",
        custom_contacts=payload.custom_contacts
    )
    return result


@router.put("/incidents/{incident_id}/location")
async def update_location(
    incident_id: str = Path(..., description="Active incident ID"),
    payload: LocationUpdateRequest = ...
):
    """
    Continuous GPS tracking endpoint.
    Frontend sends periodic GPS pings during an active emergency to trace the user.
    """
    result = sos_service.update_incident_location(
        incident_id=incident_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address
    )
    return result


@router.post("/incidents/{incident_id}/resolve")
async def resolve_emergency_incident(
    incident_id: str = Path(..., description="Incident ID to close"),
    payload: Optional[IncidentResolveRequest] = None
):
    """Closes an active emergency incident once the user is confirmed safe."""
    note = payload.resolution_note if payload else "Resolved by user"
    result = sos_service.resolve_incident(incident_id=incident_id, resolution_note=note)
    return result


@router.get("/incidents/user/{user_id}")
async def list_user_incidents(user_id: str = Path(..., description="User ID")):
    """Retrieves all past and active emergency incidents for a user."""
    incidents = sos_service.get_user_incidents(user_id.strip())
    return {
        "success": True,
        "user_id": user_id,
        "incidents_count": len(incidents),
        "incidents": incidents
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str = Path(..., description="Incident ID")):
    """Retrieves incident details along with historical location breadcrumbs."""
    incident = sos_service.get_incident_details(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "success": True,
        "incident": incident
    }
