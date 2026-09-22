import os
import sys
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app


class TestSOSPipeline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_user = "test_safety_user_01"

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_contacts_crud_and_sos_lifecycle(self):
        # 1. Add emergency contact 1 (Father)
        res1 = self.client.post("/sos/contacts", json={
            "user_id": self.test_user,
            "name": "Rajesh Sharma",
            "phone_number": "+919876543210",
            "email": "rajesh.guardian@example.com",
            "relationship": "Father",
            "is_primary": True
        })
        self.assertEqual(res1.status_code, 201)
        contact1 = res1.json()["contact"]
        contact1_id = contact1["id"]
        self.assertEqual(contact1["name"], "Rajesh Sharma")

        # 2. Add emergency contact 2 (Sister)
        res2 = self.client.post("/sos/contacts", json={
            "user_id": self.test_user,
            "name": "Priya Sharma",
            "phone_number": "+919812345678",
            "email": "priya.sister@example.com",
            "relationship": "Sister",
            "is_primary": False
        })
        self.assertEqual(res2.status_code, 201)
        contact2_id = res2.json()["contact"]["id"]

        # 3. List contacts
        list_res = self.client.get(f"/sos/contacts/{self.test_user}")
        self.assertEqual(list_res.status_code, 200)
        contacts = list_res.json()["contacts"]
        self.assertGreaterEqual(len(contacts), 2)

        # 4. Trigger Manual SOS with GPS Coordinates
        sos_res = self.client.post("/sos/trigger", json={
            "user_id": self.test_user,
            "latitude": 28.6139,
            "longitude": 77.2090,
            "address": "Connaught Place, Central Delhi",
            "trigger_source": "manual"
        })
        self.assertEqual(sos_res.status_code, 200)
        sos_data = sos_res.json()
        self.assertTrue(sos_data["success"])
        self.assertIn("incident_id", sos_data)
        self.assertEqual(sos_data["status"], "active")
        self.assertIn("https://maps.google.com/?q=28.6139,77.209", sos_data["google_maps_url"])
        incident_id = sos_data["incident_id"]

        # 5. Debounce test: immediate second trigger should be grouped into existing incident
        debounced_res = self.client.post("/sos/trigger", json={
            "user_id": self.test_user,
            "latitude": 28.6140,
            "longitude": 77.2092,
            "address": "Near Metro Gate 2",
            "trigger_source": "manual"
        })
        self.assertEqual(debounced_res.status_code, 200)
        debounced_data = debounced_res.json()
        self.assertTrue(debounced_data["debounced"])
        self.assertEqual(debounced_data["incident_id"], incident_id)

        # 6. Continuous Location Ping
        loc_res = self.client.put(f"/sos/incidents/{incident_id}/location", json={
            "latitude": 28.6150,
            "longitude": 77.2100,
            "address": "Moving towards Barakhamba Road"
        })
        self.assertEqual(loc_res.status_code, 200)
        self.assertEqual(loc_res.json()["latitude"], 28.6150)

        # 7. Get Incident Details with breadcrumbs
        details_res = self.client.get(f"/sos/incidents/{incident_id}")
        self.assertEqual(details_res.status_code, 200)
        incident_details = details_res.json()["incident"]
        self.assertEqual(incident_details["id"], incident_id)
        self.assertGreaterEqual(len(incident_details["location_history"]), 1)

        # 8. Resolve Incident
        resolve_res = self.client.post(f"/sos/incidents/{incident_id}/resolve", json={
            "resolution_note": "False alarm / User safely reached home"
        })
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()["status"], "resolved")

        # 9. Clean up contacts
        del1 = self.client.delete(f"/sos/contacts/{contact1_id}")
        self.assertEqual(del1.status_code, 200)
        del2 = self.client.delete(f"/sos/contacts/{contact2_id}")
        self.assertEqual(del2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
