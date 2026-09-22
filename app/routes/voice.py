import os
import shutil
import tempfile

from typing import Optional

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException
)

from app import config
from app.services.speaker import (
    create_voice_profile,
    verify_voice
)

from app.services.keyword import (
    extract_keyword_feature,
    detect_keyword
)

from app.services.supabase import supabase
from app.services import sos_service

router = APIRouter(
    prefix="/voice",
    tags=["Voice"]
)


@router.post("/enroll")
async def enroll_voice(
    user_id: str = Form(...),

    audio1: UploadFile = File(...),
    audio2: UploadFile = File(...),
    audio3: UploadFile = File(...)
):

    # ----------------------------------
    # Validate user ID
    # ----------------------------------

    if not user_id.strip():

        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )


    audio_files = [
        audio1,
        audio2,
        audio3
    ]


    temporary_files = []


    try:

        # ----------------------------------
        # Save uploaded recordings
        # ----------------------------------

        for audio_file in audio_files:

            if not audio_file.filename:

                raise HTTPException(
                    status_code=400,
                    detail="Invalid audio file"
                )


            suffix = os.path.splitext(
                audio_file.filename
            )[1].lower()


            if suffix not in [
                ".wav",
                ".m4a",
                ".mp3",
                ".webm"
            ]:

                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported audio format: {suffix}"
                )


            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix
            )

            with temp_file as f:

                shutil.copyfileobj(
                    audio_file.file,
                    f
                )


            temporary_files.append(
                temp_file.name
            )


        # ----------------------------------
        # Create voice profile
        # ----------------------------------

        profile_path = create_voice_profile(
            temporary_files,
            user_id
        )
    

        try:
            supabase.table("voice_profiles").upsert(
                {
                    "user_id": user_id,
                    "is_enrolled": True,
                    "enrollment_samples": len(audio_files),
                    "model_version": "ecapa-voxceleb-v1"
                },
                on_conflict="user_id"
            ).execute()
        except Exception as e:
            # Non-blocking: local profile has already been created and saved to disk
            pass


        return {

            "success": True,

            "message":
                "Voice profile created successfully",

            "user_id":
                user_id,

            "samples_used":
                len(audio_files),

            "profile_created":
                True
        }


    finally:

        # ----------------------------------
        # Delete temporary recordings
        # ----------------------------------

        for file_path in temporary_files:

            try:

                os.remove(file_path)

            except OSError:

                pass

@router.post("/verify")
async def verify_voice_endpoint(
    user_id: str = Form(...),
    audio_file: UploadFile = File(...)
):

    # ----------------------------------
    # Validate user ID
    # ----------------------------------

    if not user_id.strip():

        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )


    # ----------------------------------
    # Validate audio file
    # ----------------------------------

    if not audio_file.filename:

        raise HTTPException(
            status_code=400,
            detail="Invalid audio file"
        )


    suffix = os.path.splitext(
        audio_file.filename
    )[1].lower()


    if suffix not in [
        ".wav",
        ".m4a",
        ".mp3",
        ".webm"
    ]:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {suffix}"
        )


    temporary_file = None


    try:

        # ----------------------------------
        # Save temporary recording
        # ----------------------------------

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        )

        temporary_file = temp_file.name


        with temp_file as f:

            shutil.copyfileobj(
                audio_file.file,
                f
            )


        # ----------------------------------
        # Verify speaker
        # ----------------------------------

        try:

            result = verify_voice(
                temporary_file,
                user_id
            )

        except FileNotFoundError:

            raise HTTPException(
                status_code=404,
                detail="Voice profile not found. Enroll first."
            )


        # ----------------------------------
        # Return result
        # ----------------------------------

        return {
            "success": True,
            "user_id": user_id,
            "verified": result["verified"],
            "similarity": result["similarity"],
            "threshold": result["threshold"]
        }


    finally:

        # ----------------------------------
        # Delete temporary recording
        # ----------------------------------

        if temporary_file:

            try:

                os.remove(
                    temporary_file
                )

            except OSError:

                pass

@router.post("/trigger")
async def trigger_check(
    user_id: str = Form(...),
    audio_file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    auto_dispatch: bool = Form(True)
):

    # ==================================
    # Validate user
    # ==================================

    if not user_id.strip():

        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )


    # ==================================
    # Validate audio
    # ==================================

    if not audio_file.filename:

        raise HTTPException(
            status_code=400,
            detail="Invalid audio file"
        )


    suffix = os.path.splitext(
        audio_file.filename
    )[1].lower()


    # Support standard audio formats
    if suffix not in [
        ".wav",
        ".m4a",
        ".mp3",
        ".webm",
        ".ogg"
    ]:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {suffix}"
        )


    temporary_file = None


    try:

        # ==================================
        # Save temporary audio
        # ==================================

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        )

        temporary_file = temp_file.name


        with temp_file as f:

            shutil.copyfileobj(
                audio_file.file,
                f
            )


        # ==================================
        # KEYWORD DETECTION
        # ==================================

        feature = extract_keyword_feature(
            temporary_file
        )

        keyword_score = detect_keyword(
            feature
        )

        keyword_threshold = getattr(config, "KEYWORD_THRESHOLD", 0.5)
        keyword_detected = (
            keyword_score >= keyword_threshold
        )


        # ==================================
        # SPEAKER VERIFICATION
        # ==================================

        speaker_result = verify_voice(
            temporary_file,
            user_id
        )


        speaker_verified = (
            speaker_result["verified"]
        )


        speaker_similarity = (
            speaker_result["similarity"]
        )


        # ==================================
        # FINAL TRIGGER DECISION
        # ==================================

        trigger = (
            keyword_detected
            and speaker_verified
        )

        response_payload = {
            "success": True,
            "keyword_detected": keyword_detected,
            "keyword_score": keyword_score,
            "keyword_threshold": keyword_threshold,
            "speaker_verified": speaker_verified,
            "speaker_similarity": speaker_similarity,
            "speaker_threshold": speaker_result["threshold"],
            "trigger": trigger,
            "sos_dispatched": False
        }

        # ==================================
        # AUTOMATIC EMERGENCY SOS DISPATCH
        # ==================================
        if trigger and auto_dispatch:
            sos_res = sos_service.trigger_sos(
                user_id=user_id.strip(),
                latitude=latitude,
                longitude=longitude,
                address=address,
                trigger_source="voice",
                audio_file_path=temporary_file,
                keyword_score=keyword_score,
                speaker_similarity=speaker_similarity
            )

            response_payload.update({
                "sos_dispatched": True,
                "incident_id": sos_res.get("incident_id"),
                "status": sos_res.get("status"),
                "debounced": sos_res.get("debounced", False),
                "google_maps_url": sos_res.get("google_maps_url"),
                "contacts_notified": sos_res.get("contacts_notified", 0),
                "notification_provider": sos_res.get("notification_provider")
            })

        return response_payload


    finally:

        # ==================================
        # Delete temporary audio
        # ==================================

        if temporary_file:

            try:

                os.remove(
                    temporary_file
                )

            except OSError:

                pass