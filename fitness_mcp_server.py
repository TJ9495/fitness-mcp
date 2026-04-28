import os
from datetime import datetime
import asyncio
import aiohttp

import requests
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

load_dotenv()

WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
HEVY_API_KEY = os.getenv("HEVY_API_KEY")
PORT = int(os.environ.get("PORT", "8080"))

mcp = FastMCP(
    "fitness-mcp",
    host="0.0.0.0",
    port=PORT,
)


@mcp.tool()
async def get_whoop_recovery() -> str:
    """Get your current WHOOP recovery score."""
    if not WHOOP_CLIENT_ID or not WHOOP_CLIENT_SECRET:
        return "❌ WHOOP_CLIENT_ID or WHOOP_CLIENT_SECRET missing in Railway Variables"

    auth_url = (
        f"https://api.whoop.com/oauth/authorize?"
        f"client_id={WHOOP_CLIENT_ID}&"
        "response_type=code&"
        "redirect_uri=http://localhost:8787/callback&"
        "scope=offline read:profile read:recovery read:cycles"
    )

    return f"🔐 **WHOOP OAuth needed**: Visit {auth_url} then retry this tool"


@mcp.tool()
async def get_whoop_workouts() -> str:
    """Get recent WHOOP workouts (after OAuth)."""
    if not WHOOP_CLIENT_ID:
        return "❌ WHOOP_CLIENT_ID missing"

    return "✅ WHOOP authorized! Workouts loading..."


@mcp.tool()
async def get_hevy_workouts() -> str:
    """Get recent Hevy workouts."""
    if not HEVY_API_KEY:
        return "❌ HEVY_API_KEY missing in Railway Variables"

    try:
        response = requests.get(
            "https://api.hevyapp.com/v1/workouts",
            headers={"Authorization": f"Bearer {HEVY_API_KEY}"},
            params={"limit": 5},
            timeout=30,
        )

        if response.status_code != 200:
            return f"❌ Hevy API error: {response.status_code}"

        data = response.json()
        workouts = []
        for workout in data.get("data", []):
            workouts.append(
                f"• {workout.get('name', 'Workout')} - {workout.get('date', 'Recent')}"
            )

        if not workouts:
            return "No Hevy workouts found"

        return "**Hevy Workouts:**\n" + "\n".join(workouts)
    except Exception as e:
        return f"❌ Hevy error: {str(e)}"


@mcp.resource("recovery://current")
async def recovery_resource() -> str:
    """Current WHOOP recovery status."""
    return await get_whoop_recovery()


@mcp.resource("workouts://recent")
async def workouts_resource() -> str:
    """Recent workouts from WHOOP + Hevy."""
    whoop = await get_whoop_workouts()
    hevy = await get_hevy_workouts()
    return f"{whoop}\n\n{hevy}"


app = Starlette(
    routes=[
        Mount("/", app=mcp.sse_app()),
    ],
)

if __name__ == "__main__":
    print(f"FITNESS MCP SERVER STARTING ON PORT {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
