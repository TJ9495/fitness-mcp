print("WHOOP CLIENT LOADED")
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

load_dotenv(dotenv_path=ENV_PATH, override=True)

CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")

EXPIRES_AT_FILE = BASE_DIR / ".whoop_token_expiry"

def read_expires_at():
    if EXPIRES_AT_FILE.exists():
        try:
            return float(EXPIRES_AT_FILE.read_text().strip())
        except:
            return 0
    return 0

def write_expires_at(expires_at):
    EXPIRES_AT_FILE.write_text(str(expires_at))

def update_env_value(key, value):
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break

    if not updated:
        lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines) + "\n")

def save_tokens(access_token, refresh_token, expires_in):
    global ACCESS_TOKEN, REFRESH_TOKEN
    ACCESS_TOKEN = access_token
    REFRESH_TOKEN = refresh_token

    update_env_value("WHOOP_ACCESS_TOKEN", access_token)
    update_env_value("WHOOP_REFRESH_TOKEN", refresh_token)

    expires_at = time.time() + int(expires_in) - 120
    write_expires_at(expires_at)

def refresh_access_token():
    global ACCESS_TOKEN, REFRESH_TOKEN

    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "offline",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=30)
    response.raise_for_status()

    token_data = response.json()

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in", 3600)

    save_tokens(access_token, refresh_token, expires_in)
    return access_token

def get_valid_access_token():
    expires_at = read_expires_at()

    if not ACCESS_TOKEN or time.time() >= expires_at:
        return refresh_access_token()

    return ACCESS_TOKEN

def whoop_get(url):
    access_token = get_valid_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 401:
        access_token = refresh_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        response = requests.get(url, headers=headers, timeout=30)

    return response

# WHOOP Data Endpoints
def get_profile():
    return whoop_get("https://api.prod.whoop.com/developer/v1/user/profile/basic")

def get_cycles(limit=1):
    return whoop_get(f"https://api.prod.whoop.com/developer/v1/cycle?limit={limit}")

def get_cycle_recovery(cycle_id):
    return whoop_get(f"https://api.prod.whoop.com/developer/v1/cycle/{cycle_id}/recovery")

def get_workouts(limit=1):
    return whoop_get(f"https://api.prod.whoop.com/developer/v1/activity/workout?limit={limit}")

def get_sleep(limit=1):
    return whoop_get(f"https://api.prod.whoop.com/developer/v1/activity/sleep?limit={limit}")

def get_body_measurements():
    return whoop_get("https://api.prod.whoop.com/developer/v1/user/measurement/body")

if __name__ == "__main__":
    # Test all endpoints
    print("=== WHOOP DATA TEST ===")
    
    print("\n1. Profile:")
    profile = get_profile()
    print(f"Status: {profile.status_code}")
    
    print("\n2. Cycles:")
    cycles = get_cycles()
    print(f"Status: {cycles.status_code}")
    
    print("\n3. Body measurements:")
    body = get_body_measurements()
    print(f"Status: {body.status_code}")
    
    print("\n4. Workouts:")
    workouts = get_workouts()
    print(f"Status: {workouts.status_code}")
    
    print("\n5. Sleep:")
    sleep = get_sleep()
    print(f"Status: {sleep.status_code}")