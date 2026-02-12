import requests
import json
import sys

try:
    url = "http://localhost:8001/api/simulation/simulate"
    payload = {
        "subject": "Test Email",
        "sender": "test@example.com",
        "body": "This is a test to verify the simulation module."
    }
    headers = {"Content-Type": "application/json"}
    
    # We expect this to fail if AI key is missing, or succeed if it is present.
    # But at least it should return a response (even 500), not Connection Refused.
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
except Exception as e:
    print(f"Error: {e}")
