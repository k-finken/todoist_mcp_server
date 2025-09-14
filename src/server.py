#!/usr/bin/env python3
import os, httpx, json
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.middleware import Middleware, MiddlewareContext
from dotenv import load_dotenv
import fastmcp

load_dotenv()

TODOIST_API = "https://api.todoist.com/api/v1"
TOKEN = os.environ["TODOIST_API_TOKEN"]  # put your token in Render/Heroku env
BEARER_TOKEN = os.environ.get("MCP_BEARER_TOKEN")  # Bearer token for MCP server authentication

class RequestLoggingMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        """Log incoming request details."""
        print("--- Incoming Request ---")
        print(f"Method: {context.method}")
        print(f"Source: {context.source}")
        
        if hasattr(context, 'message'):
            print(f"Message: {context.message}")

        if hasattr(context, 'fastmcp_context'):
            request = context.fastmcp_context.get_http_request()
            if request:
                print("--- HTTP Request ---")
                print(f"Headers: {dict(request.headers)}")
                try:
                    body = await request.json()
                    print(f"Body: {json.dumps(body, indent=2)}")
                except json.JSONDecodeError:
                    body = await request.body()
                    print(f"Body: {body.decode(errors='ignore')}")


        print("------------------------")
        
        return await call_next(context)

# Configure authentication using FastMCP's built-in token verification
auth_verifier = None
if BEARER_TOKEN:
    auth_verifier = StaticTokenVerifier(
        tokens={
            "kyle-dev-token": {
                "client_id": "kfinken@finkenfive.com",
            },
        },
    )

mcp = FastMCP("Todoist MCP", auth=auth_verifier)
mcp.add_middleware(RequestLoggingMiddleware())

def auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def format_task_for_llm(task: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw Todoist task to LLM-friendly format with only essential information."""
    formatted_task = {
        "id": task["id"],
        "content": task["content"],
        "completed": task["checked"],
    }
    
    # Add due date if present
    if task.get("due"):
        formatted_task["due_date"] = task["due"]["string"]
        formatted_task["is_overdue"] = task["due"]["date"] < "2025-09-14"  # Today's date
    
    # Add priority (1=normal, 2=high, 3=very high, 4=urgent)
    priority_map = {1: "normal", 2: "high", 3: "very high", 4: "urgent"}
    formatted_task["priority"] = priority_map.get(task["priority"], "normal")
    
    # Add description if present
    if task.get("description"):
        formatted_task["description"] = task["description"]
    
    return formatted_task

@mcp.tool(description="List today + overdue tasks in LLM-friendly format",)
async def todoist_list_today(limit: int = 25) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{TODOIST_API}/tasks/filter", headers=auth_headers(),
                             params={"query": "(today | overdue)", "limit": limit})
        r.raise_for_status()
        raw_tasks = r.json().get("results", [])
        
        # Transform to LLM-friendly format
        formatted_tasks = [format_task_for_llm(task) for task in raw_tasks]
        return formatted_tasks

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), stateless_http=True)