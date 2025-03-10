from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import uuid
import json
import asyncio
from typing import Dict, Optional
from pathlib import Path

from app.agent import ToolCallAgent
from app.logger import logger
from app.schema import Task, TaskEvent, TaskEventType, TaskStatus

app = FastAPI()

# Mount static files
static_path = Path(__file__).parent / "static"
templates_path = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

# Store tasks and their events
tasks: Dict[str, Task] = {}
task_events: Dict[str, list] = {}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/tasks")
async def get_tasks():
    return list(tasks.values())

@app.post("/tasks")
async def create_task(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        
        # Create a new task
        task_id = str(uuid.uuid4())
        task = Task(id=task_id, prompt=prompt, status=TaskStatus.PENDING)
        tasks[task_id] = task
        task_events[task_id] = []
        
        # Process task in background
        asyncio.create_task(process_task(task))
        
        return task
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found"}
        )
    return task

@app.get("/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    events = task_events.get(task_id, [])
    if events is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found"}
        )
    return events

async def process_task(task: Task):
    try:
        # Update task status
        task.status = TaskStatus.RUNNING
        tasks[task.id] = task
        
        # Create agent
        agent = ToolCallAgent()
        
        # Add initial event
        event = TaskEvent(
            type=TaskEventType.THINKING,
            content="开始处理任务..."
        )
        task_events[task.id].append(event)
        
        # Run agent
        result = await agent.run(task.prompt)
        
        # Add result event
        event = TaskEvent(
            type=TaskEventType.COMPLETE,
            content=result
        )
        task_events[task.id].append(event)
        
        # Update task status
        task.status = TaskStatus.COMPLETED
        tasks[task.id] = task
        
    except Exception as e:
        logger.error(f"Error processing task: {str(e)}")
        # Add error event
        event = TaskEvent(
            type=TaskEventType.ERROR,
            content=f"处理任务时出错: {str(e)}"
        )
        task_events[task.id].append(event)
        
        # Update task status
        task.status = TaskStatus.FAILED
        tasks[task.id] = task

# For local development only
if __name__ == "__main__":
    uvicorn.run("app:app", host="localhost", port=5172, reload=True)
