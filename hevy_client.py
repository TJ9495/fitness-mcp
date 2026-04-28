import os
from pathlib import Path
import json
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com"


def get_hevy_workouts(page=1, page_size=10) -> Dict[str, Any]:
    """Fetch Hevy workouts with correct api-key auth."""
    if not HEVY_API_KEY:
        raise ValueError("Missing HEVY_API_KEY in .env")

    headers = {
        "api-key": HEVY_API_KEY,
        "Accept": "application/json",
    }

    response = requests.get(
        f"{BASE_URL}/v1/workouts",
        headers=headers,
        params={"page": page, "pageSize": page_size},
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_recent_workouts(limit=5) -> List[Dict[str, Any]]:
    """Get your most recent workouts."""
    data = get_hevy_workouts(page_size=limit)
    return data.get("workouts", [])


if __name__ == "__main__":
    print("HEVY CLIENT LOADED ✅")
    
    workouts = get_recent_workouts()
    print(f"Found {len(workouts)} recent workouts:")
    
    for workout in workouts:
        title = workout.get("title", "Untitled")
        date = workout["start_time"][:10]  # YYYY-MM-DD
        duration = workout.get("duration_minutes", "N/A")
        print(f"• {title} ({date}) - {duration}min")
    
    print("\n✅ Hevy API connected successfully!")