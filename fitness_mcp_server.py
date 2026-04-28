import os
from datetime import datetime
from mcp.server.fastmcp import FastMCP

import whoop_client
import hevy_client

mcp = FastMCP("fitness-insights")


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {
            "error": "Invalid JSON response",
            "status_code": getattr(response, "status_code", None),
        }


@mcp.tool()
def get_profile():
    """Get WHOOP user profile."""
    resp = whoop_client.get_profile()
    return {
        "status_code": resp.status_code,
        "data": safe_json(resp),
    }


@mcp.tool()
def get_body_measurements():
    """Get WHOOP body measurements."""
    resp = whoop_client.get_body_measurements()
    return {
        "status_code": resp.status_code,
        "data": safe_json(resp),
    }


@mcp.tool()
def get_recent_cycles(limit: int = 7):
    """Get recent WHOOP cycles with strain."""
    resp = whoop_client.get_cycles(limit=limit)
    data = safe_json(resp)
    records = data.get("records", data.get("cycles", [])) if isinstance(data, dict) else []

    cycles = []
    for cycle in records[:limit]:
        cycles.append({
            "id": cycle.get("id"),
            "strain": cycle.get("score", {}).get("strain"),
            "start": cycle.get("start"),
            "end": cycle.get("end"),
        })

    return {
        "status_code": resp.status_code,
        "count": len(cycles),
        "cycles": cycles,
    }


@mcp.tool()
def get_recent_hevy_workouts(limit: int = 5):
    """Get recent Hevy workouts."""
    data = hevy_client.get_hevy_workouts(page=1, page_size=limit)
    workouts = data.get("workouts", [])

    formatted = []
    for workout in workouts:
        start_time = workout.get("start_time", "")
        end_time = workout.get("end_time", "")
        duration_min = None

        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration_min = int((end_dt - start_dt).total_seconds() / 60)
            except Exception:
                duration_min = None

        formatted.append({
            "id": workout.get("id"),
            "title": workout.get("title"),
            "date": start_time[:10] if start_time else None,
            "duration_min": duration_min,
            "exercises": [
                ex.get("title")
                for ex in workout.get("exercises", [])[:5]
                if ex.get("title")
            ],
        })

    return {
        "count": len(formatted),
        "workouts": formatted,
    }


@mcp.tool()
def get_training_summary():
    """Get a combined WHOOP + Hevy summary."""
    cycles_resp = whoop_client.get_cycles(limit=7)
    cycles_data = safe_json(cycles_resp)
    cycle_records = cycles_data.get("records", cycles_data.get("cycles", [])) if isinstance(cycles_data, dict) else []

    strains = []
    for cycle in cycle_records[:7]:
        strain = cycle.get("score", {}).get("strain")
        if strain is not None:
            strains.append(float(strain))

    avg_strain_3 = round(sum(strains[:3]) / min(len(strains[:3]), 3), 1) if strains[:3] else None
    avg_strain_7 = round(sum(strains) / len(strains), 1) if strains else None

    hevy_data = hevy_client.get_hevy_workouts(page=1, page_size=5)
    workouts = hevy_data.get("workouts", [])

    total_minutes = 0
    workout_titles = []
    for workout in workouts:
        start_time = workout.get("start_time", "")
        end_time = workout.get("end_time", "")
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                total_minutes += int((end_dt - start_dt).total_seconds() / 60)
            except Exception:
                pass
        if workout.get("title"):
            workout_titles.append(workout["title"])

    return {
        "avg_strain_3_cycles": avg_strain_3,
        "avg_strain_7_cycles": avg_strain_7,
        "recent_hevy_workout_count": len(workouts),
        "recent_hevy_total_minutes": total_minutes,
        "recent_hevy_titles": workout_titles[:5],
    }


@mcp.tool()
def get_rehab_progress_notes():
    """Summarize recent training pattern for rehab-oriented review."""
    hevy_data = hevy_client.get_hevy_workouts(page=1, page_size=10)
    workouts = hevy_data.get("workouts", [])

    machine_sessions = 0
    barbell_sessions = 0

    for workout in workouts:
        exercise_titles = [
            (ex.get("title") or "").lower()
            for ex in workout.get("exercises", [])
        ]

        if any("machine" in title for title in exercise_titles):
            machine_sessions += 1
        if any("barbell" in title for title in exercise_titles):
            barbell_sessions += 1

    return {
        "recent_sessions_checked": len(workouts),
        "machine_sessions": machine_sessions,
        "barbell_sessions": barbell_sessions,
        "interpretation": "Recent training appears machine-heavy, which may fit a post-surgery or lower-joint-stress phase.",
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"FITNESS MCP SERVER STARTING ON PORT {port}...")
    mcp.run(transport="http", host="0.0.0.0", port=port)
