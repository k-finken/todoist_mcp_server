#!/usr/bin/env python3
import os, httpx, json
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv
import fastmcp

load_dotenv()

TODOIST_API = "https://api.todoist.com/api/v1"
TOKEN = os.environ.get("TODOIST_API_TOKEN")

mcp = FastMCP("Todoist MCP")

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
        # Compare with today's date in YYYY-MM-DD format
        today = date.today().strftime("%Y-%m-%d")
        formatted_task["is_overdue"] = task["due"]["date"] < today
    
    # Add priority (1=normal, 2=high, 3=very high, 4=urgent)
    priority_map = {1: "normal", 2: "high", 3: "very high", 4: "urgent"}
    formatted_task["priority"] = priority_map.get(task["priority"], "normal")
    
    # Add description if present
    if task.get("description"):
        formatted_task["description"] = task["description"]
    
    return formatted_task

@mcp.tool(description="List todoist tasks for today.",)
async def todoist_list_today(limit: int = 25) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            print(f"Making request to Todoist API with query: (today), limit: {limit}")
            r = await client.get(f"{TODOIST_API}/tasks/filter", headers=auth_headers(),
                                 params={"query": "(today)", "limit": limit})
            
            print(f"Todoist API response status: {r.status_code}")
            if r.status_code != 200:
                print(f"Todoist API error response: {r.text}")
            
            r.raise_for_status()
            response_data = r.json()
            raw_tasks = response_data.get("results", [])
            
            print(f"Retrieved {len(raw_tasks)} tasks from Todoist")
            
            formatted_tasks = [format_task_for_llm(task) for task in raw_tasks]
            return formatted_tasks
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error calling Todoist API: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Todoist API returned {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"Unexpected error calling Todoist API: {str(e)}")
        raise Exception(f"Failed to fetch tasks: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), stateless_http=True)