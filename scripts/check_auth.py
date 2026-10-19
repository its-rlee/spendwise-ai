
import os
from getpass import getpass

import httpx
from dotenv import load_dotenv

load_dotenv()

url = os.environ["SUPABASE_URL"].rstrip("/")
key = os.environ["SUPABASE_PUBLISHABLE_KEY"]

email = input("Test account email: ")
password = getpass("Test account password: ")

with httpx.Client(timeout=15) as client:
    login = client.post(
        f"{url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": key},
        json={
            "email": email,
            "password": password,
        },
    )

    login.raise_for_status()
    token = login.json()["access_token"]

    response = client.get(
        "http://127.0.0.1:8000/api/v1/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    print("API status:", response.status_code)
    print("API response:", response.json())
