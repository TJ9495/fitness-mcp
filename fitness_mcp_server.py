import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.sse import sse_app
from mcp.types import (
    ExecuteToolRequest,
    ExecuteToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    Resource,
    ListResourcesRequest,
    ListResourcesResult,
    ReadResourceRequest,
    ReadResourceResult,
    UpdateSettingsRequest,
)
from starlette.applications import Starlette
from starlette.routing import Mount
from pydantic import AnyUrl

load_dotenv()

WHOOP_ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
WHOOP_USER_ID = os.getenv("WHOOP_USER_ID")

mcp = Server("fitness-mcp")

# ==================== TOOLS ====================

@mcp.tool()
def get_whoop_recovery() -> str:
    """Get your current WHOOP recovery score, strain, and sleep data."""
    if not WHOOP_ACCESS_TOKEN or not WHOOP_USER_ID:
        return "❌ WHOOP_ACCESS_TOKEN or WHOOP_USER_ID missing"
    
    headers = {
        "Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}",
        "Whoop-User-ID": WHOOP_USER_ID
    }
    
    url = f"https://api.whoop.com/graphql/v1"
    
    query = """
    query GetRecovery($userId: String!) {
        user(id: $userId) {
            id
            cycles(sort: {key: START_DATE_TIME, order: DESC}, first: 1) {
                edges {
                    node {
                        recovery
                        strain
                        sleep_needed
                        sleep_performed
                        sleep_deficit
                        sleep_efficiency
                        restlessness
                        sleep_latency
                        sleep_performance
                        start_date_time
                        end_date_time
                    }
                }
            }
        }
    }
    """
    
    variables = {"userId": WHOOP_USER_ID}
    
    response = requests.post(
        url, 
        json={"query": query, "variables": variables},
        headers=headers
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
        
        return f"""
{recovery_emoji} **Recovery: {recovery}%**
💪 **Strain: {strain:.0f}**
😴 **Sleep Performed: {cycle['sleep_performed']:.1f}h** (Needed: {cycle['sleep_needed']:.1f}h)
📊 **Efficiency: {cycle['sleep_efficiency']:.0f}%**
        """.strip()
    except (KeyError, IndexError):
        return "❌ No recent data found"

@mcp.tool()
def get_workouts() -> str:
    """Get your recent workouts from WHOOP."""
    if not WHOOP_ACCESS_TOKEN or not WHOOP_USER_ID:
        return "❌ WHOOP credentials missing"
    
    headers = {
        "Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}",
        "Whoop-User-ID": WHOOP_USER_ID
    }
    
    url = f"https://api.whoop.com/graphql/v1"
    
    query = """
    query GetWorkouts($userId: String!) {
        user(id: $userId) {
            id
            activities(sort: {key: START_DATE_TIME, order: DESC}, first: 5) {
                edges {
                    node {
                        id
                        name
                        strain
                        duration
                        calories
                        start_date_time
                        end_date_time
                        type
                    }
                }
            }
        }
    }
    """
    
    response = requests.post(url, json={"query": query, "userId": WHOOP_USER_ID}, headers=headers)
    
    if response.status_code != 200:
        return f"❌ API Error: {response.status_code}"
    
    data = response.json()
    activities = data["data"]["user"]["activities"]["edges"]
    
    if not activities:
        return "No recent workouts found"
    
    workouts = []
    for edge in activities:
        activity = edge["node"]
        duration = (datetime.fromisoformat(activity["end_date_time"].replace('Z', '+00:00')) 
                   - datetime.fromisoformat(activity["start_date_time"].replace('Z', '+00:00'))).total_seconds() / 3600
        workouts.append(f"• **{activity['name']}** ({duration:.1f}h): {activity['strain']:.0f} strain")
    
    return "**Recent Workouts:**\n" + "\n".join(workouts)

# ==================== RESOURCES ====================

@mcp.resource("recovery://current")
async def get_recovery() -> str:
    """Current WHOOP recovery data."""
    return await mcp.execute_tool(ExecuteToolRequest(name="get_whoop_recovery"))

@mcp.resource("workouts://recent")
async def get_recent_workouts() -> str:
    """Recent workouts from WHOOP."""
    return await mcp.execute_tool(ExecuteToolRequest(name="get_workouts"))

# ==================== SERVER SETUP ====================

@mcp.list_tools()
async def handle_list_tools(
    request: ListToolsRequest,
) -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="get_whoop_recovery",
                description="Get your current WHOOP recovery score, strain, and sleep data.",
                inputSchema={},
            ),
            Tool(
                name="get_workouts",
                description="Get your recent workouts from WHOOP.",
                inputSchema={},
            ),
        ]
    )

@mcp.list_resources()
async def handle_list_resources(
    request: ListResourcesRequest,
) -> ListResourcesResult:
    return ListResourcesResult(
        resources=[
            Resource(
                uri="recovery://current",
                name="Current Recovery",
                description="Your latest WHOOP recovery score and sleep data",
                mimeType="text/markdown",
            ),
            Resource(
                uri="workouts://recent", 
                name="Recent Workouts",
                description="Your 5 most recent WHOOP workouts",
                mimeType="text/markdown",
            ),
        ]
    )

@mcp.read_resource()
async def handle_read_resource(
    request: ReadResourceRequest,
) -> ReadResourceResult:
    if request.uri == "recovery://current":
        return ReadResourceResult(
            uri=request.uri,
            mimeType="text/markdown",
            data=await get_recovery(),
        )
    elif request.uri == "workouts://recent":
        return ReadResourceResult(
            uri=request.uri,
            mimeType="text/markdown",
            data=await get_recent_workouts(),
        )
    raise ValueError(f"Unknown resource: {request.uri}")

# ==================== STREAMABLE HTTP ====================

from mcp.server.fastmcp import FastMCP

fmcp = FastMCP(mcp)

@mcp.settings()
async def handle_settings_update(request: UpdateSettingsRequest) -> None:
    pass

# ==================== STARLETTE APP ====================

app = Starlette(
    routes=[
        Mount("/mcp", app=sse_app(mcp)),
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"FITNESS MCP SERVER STARTING ON PORT {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
