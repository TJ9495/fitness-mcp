import os
from datetime import datetime

import requests
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

load_dotenv()

WHOOP_ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
WHOOP_USER_ID = os.getenv("WHOOP_USER_ID")

mcp = FastMCP("fitness-mcp", stateless_http=True)


@mcp.tool()
def get_whoop_recovery() -> str:
    """Get your current WHOOP recovery score, strain, and sleep data."""
    if not WHOOP_ACCESS_TOKEN or not WHOOP_USER_ID:
        return "❌ WHOOP_ACCESS_TOKEN or WHOOP_USER_ID missing"

    headers = {
        "Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}",
        "Whoop-User-ID": WHOOP_USER_ID,
    }

    query = """
    query GetRecovery($userId: String!) {
        user(id: $userId) {
            cycles(sort: {key: START_DATE_TIME, order: DESC}, first: 1) {
                edges {
                    node {
                        recovery
                        strain
                        sleep_needed
                        sleep_performed
                        sleep_efficiency
                    }
                }
            }
        }
    }
    """

    response = requests.post(
        "https://api.whoop.com/graphql/v1",
        json={"query": query, "variables": {"userId": WHOOP_USER_ID}},
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        return f"❌ API Error: {response.status_code}"

    data = response.json()

    if "errors" in data:
        return f"❌ GraphQL Error: {data['errors']}"

    try:
        cycle = data["data"]["user"]["cycles"]["edges"][0]["node"]
        recovery = cycle["recovery"]
        strain = cycle["strain"]
        recovery_emoji = "🟢" if recovery > 67 else "🟡" if recovery > 33 else "🔴"

        return (
            f"{recovery_emoji} Recovery: {recovery}%\n"
            f"💪 Strain: {strain:.0f}\n"
            f"😴 Sleep Performed: {cycle['sleep_performed']:.1f}h "
            f"(Needed: {cycle['sleep_needed']:.1f}h)\n"
            f"📊 Efficiency: {cycle['sleep_efficiency']:.0f}%"
        )
    except (KeyError, IndexError, TypeError):
        return "❌ No recent recovery data found"


@mcp.tool()
def get_workouts() -> str:
    """Get your recent workouts from WHOOP."""
    if not WHOOP_ACCESS_TOKEN or not WHOOP_USER_ID:
        return "❌ WHOOP credentials missing"

    headers = {
        "Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}",
        "Whoop-User-ID": WHOOP_USER_ID,
    }

    query = """
    query GetWorkouts($userId: String!) {
        user(id: $userId) {
            activities(sort: {key: START_DATE_TIME, order: DESC}, first: 5) {
                edges {
                    node {
                        name
                        strain
                        start_date_time
                        end_date_time
                    }
                }
            }
        }
    }
    """

    response = requests.post(
        "https://api.whoop.com/graphql/v1",
        json={"query": query, "variables": {"userId": WHOOP_USER_ID}},
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        return f"❌ API Error: {response.status_code}"

    data = response.json()

    if "errors" in data:
        return f"❌ GraphQL Error: {data['errors']}"

    try:
        activities = data["data"]["user"]["activities"]["edges"]
    except (KeyError, TypeError):
        return "❌ Could not read workout data"

    if not activities:
        return "No recent workouts found"

    workouts = []
    for edge in activities:
        activity = edge["node"]
        start_time = datetime.fromisoformat(activity["start_date_time"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(activity["end_date_time"].replace("Z", "+00:00"))
        duration = (end_time - start_time).total_seconds() / 3600
        workouts.append(f"• {activity['name']} ({duration:.1f}h): {activity['strain']:.0f} strain")

    return "Recent Workouts:\n" + "\n".join(workouts)


@mcp.resource("recovery://current")
def recovery_resource() -> str:
    """Current WHOOP recovery data."""
    return get_whoop_recovery()


@mcp.resource("workouts://recent")
def workouts_resource() -> str:
    """Recent workouts from WHOOP."""
    return get_workouts()


app = Starlette(
    routes=[
        Mount("/", app=mcp.streamable_http_app()),
    ]
)

app = CORSMiddleware(
    app,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"FITNESS MCP SERVER STARTING ON PORT {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
