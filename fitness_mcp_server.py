import os
from datetime import datetime
import asyncio

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
    try:
        from whoopy import WhoopClient
        
        client = WhoopClient.auth_flow(
            client_id=WHOOP_CLIENT_ID,
            client_secret=WHOOP_CLIENT_SECRET,
            redirect_uri="http://localhost:8787/callback"
        )
        
        cycles = client.cycle.collection(limit=1)
        if not cycles:
            return "No recent WHOOP data"
        
        cycle = cycles[0]
        recovery = cycle.recovery
        strain = cycle.strain
        emoji = "🟢" if recovery > 67 else "🟡" if recovery > 33 else "🔴"
        
        return (
            f"{emoji} **Recovery: {recovery}%**\n"
            f"💪 **Strain: {strain:.0f}**\n"
            f"😴 **Sleep Performance: {cycle.sleep.performance:.1f}%**"
        )
    except ImportError:
        return "❌ Install whoopy: pip install whoopy"
    except Exception as e:
        return f"OAuth needed: {str(e)}"


@mcp.tool()
async def get_workouts() -> str:
    """Get recent workouts from WHOOP and Hevy."""
    workouts = []
    
    # WHOOP workouts
    try:
        from whoopy import WhoopClient
        client = WhoopClient.auth_flow(
            WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET, "http://localhost:8787/callback"
        )
        activities = client.activity.collection(limit=3)
        for activity in activities:
            duration = (activity.end_time - activity.start_time).total_seconds() / 3600
            workouts.append(f"**WHOOP** {activity.name} ({duration:.1f}h): {activity.strain:.0f}")
    except:
        pass
    
    # Hevy workouts (preserved)
    if HEVY_API_KEY:
        try:
            response = requests.get(
                "https://api.hevyapp.com/v1/workouts",
                headers={"Authorization": f"Bearer {HEVY_API_KEY}"},
                params={"limit": 3}
            )
            if response.status_code == 200:
                hevy_workouts = response.json().get("data", [])
                for workout in hevy_workouts:
                    workouts.append(f"**Hevy** {workout.get('name', 'Workout')} - {workout.get('date', 'Recent')}")
        except:
            pass
    
    return "**Recent Workouts:**\n" + "\n".join(workouts[:6]) or "No workouts found"


@mcp.resource("recovery://current")
async def recovery_resource() -> str:
    """Current WHOOP recovery data."""
    return await get_whoop_recovery()


@mcp.resource("workouts://recent")
async def workouts_resource() -> str:
    """Recent workouts from WHOOP + Hevy."""
    return await get_workouts()


app = Starlette(
    routes=[
        Mount("/", app=mcp.sse_app()),
    ],
)

if __name__ == "__main__":
    print(f"FITNESS MCP SERVER STARTING ON PORT {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
