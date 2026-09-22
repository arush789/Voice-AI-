import os
import sys
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app


class TestVoiceSOSIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_user = "voice_integration_user"
        self.dataset_dir = os.path.join("datasets", "keyword", "positive")

    def test_voice_enrollment_and_voice_sos_trigger(self):
        # Verify dataset exists
        audio1_path = os.path.join(self.dataset_dir, "raksha (1).wav")
        audio2_path = os.path.join(self.dataset_dir, "raksha (2).wav")
        audio3_path = os.path.join(self.dataset_dir, "raksha (3).wav")
        test_audio_path = os.path.join(self.dataset_dir, "raksha (4).wav")

        if not (os.path.exists(audio1_path) and os.path.exists(test_audio_path)):
            self.skipTest("Positive keyword dataset audio files not found.")

        # 1. Enroll user voice profile
        with open(audio1_path, "rb") as a1, open(audio2_path, "rb") as a2, open(audio3_path, "rb") as a3:
            enroll_res = self.client.post(
                "/voice/enroll",
                data={"user_id": self.test_user},
                files={
                    "audio1": ("audio1.wav", a1, "audio/wav"),
                    "audio2": ("audio2.wav", a2, "audio/wav"),
                    "audio3": ("audio3.wav", a3, "audio/wav")
                }
            )

        self.assertEqual(enroll_res.status_code, 200)
        enroll_data = enroll_res.json()
        self.assertTrue(enroll_data["success"])
        self.assertTrue(enroll_data["profile_created"])

        # 2. Add an emergency contact for this user
        contact_res = self.client.post("/sos/contacts", json={
            "user_id": self.test_user,
            "name": "Mom",
            "phone_number": "+919811122233",
            "email": "mom.safety@example.com",
            "relationship": "Mother",
            "is_primary": True
        })
        self.assertEqual(contact_res.status_code, 201)

        # 3. Trigger Voice SOS with a "Raksha" recording + GPS coordinates
        with open(test_audio_path, "rb") as test_audio:
            trigger_res = self.client.post(
                "/voice/trigger",
                data={
                    "user_id": self.test_user,
                    "latitude": 28.5355,
                    "longitude": 77.3910,
                    "address": "Sector 62, Noida, UP",
                    "auto_dispatch": "true"
                },
                files={
                    "audio_file": ("test_raksha.wav", test_audio, "audio/wav")
                }
            )

        self.assertEqual(trigger_res.status_code, 200)
        trigger_data = trigger_res.json()

        print("\n--- VOICE TRIGGER RESPONSE ---")
        print(trigger_data)

        self.assertTrue(trigger_data["success"])
        self.assertTrue(trigger_data["keyword_detected"], f"Keyword score {trigger_data.get('keyword_score')} below threshold")
        self.assertTrue(trigger_data["speaker_verified"], f"Speaker similarity {trigger_data.get('speaker_similarity')} below threshold")
        self.assertTrue(trigger_data["trigger"])
        self.assertTrue(trigger_data["sos_dispatched"])
        self.assertIn("incident_id", trigger_data)
        self.assertIn("https://maps.google.com/?q=28.5355,77.391", trigger_data["google_maps_url"])

        # 4. Verify Audio Evidence File was saved
        incident_id = trigger_data["incident_id"]
        evidence_file = os.path.join("evidence", "audio", f"{incident_id}.wav")
        self.assertTrue(os.path.exists(evidence_file), f"Evidence file {evidence_file} was not saved")
        self.assertGreater(os.path.getsize(evidence_file), 0)


if __name__ == "__main__":
    unittest.main()
