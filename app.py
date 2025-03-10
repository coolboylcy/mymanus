from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import uuid
import json
import asyncio
from typing import Dict, Optional
import os
from pathlib import Path

from app.agent import ToolCallAgent
from app.logger import logger
from app.schema import Task, TaskEvent, TaskEventType, TaskStatus

app = FastAPI()

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

# Mount static files with absolute paths
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"

try:
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    templates = Jinja2Templates(directory=str(templates_path))
except Exception as e:
    logger.error(f"Error mounting static files: {str(e)}")

# In-memory storage
tasks: Dict[str, Task] = {}
task_events: Dict[str, list] = {}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.get("/tasks")
async def get_tasks():
    try:
        return list(tasks.values())
    except Exception as e:
        logger.error(f"Error getting tasks: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.post("/tasks")
async def create_task(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        if not prompt:
            return JSONResponse(
                status_code=400,
                content={"error": "Prompt is required"}
            )
        
        task_id = str(uuid.uuid4())
        task = Task(id=task_id, prompt=prompt, status=TaskStatus.PENDING)
        tasks[task_id] = task
        task_events[task_id] = []
        
        # Process task in background
        background_tasks = asyncio.create_task(process_task(task))
        
        return task
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    try:
        task = tasks.get(task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found"}
            )
        return task
    except Exception as e:
        logger.error(f"Error getting task: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.get("/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    try:
        events = task_events.get(task_id)
        if events is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found"}
            )
        return events
    except Exception as e:
        logger.error(f"Error getting task events: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

async def process_task(task: Task):
    try:
        task.status = TaskStatus.RUNNING
        tasks[task.id] = task
        
        agent = ToolCallAgent()
        
        event = TaskEvent(
            type=TaskEventType.THINKING,
            content="开始处理任务..."
        )
        task_events[task.id].append(event)
        
        result = await agent.run(task.prompt)
        
        event = TaskEvent(
            type=TaskEventType.COMPLETE,
            content=result
        )
        task_events[task.id].append(event)
        
        task.status = TaskStatus.COMPLETED
        tasks[task.id] = task
        
    except Exception as e:
        logger.error(f"Error processing task: {str(e)}")
        event = TaskEvent(
            type=TaskEventType.ERROR,
            content=f"处理任务时出错: {str(e)}"
        )
        task_events[task.id].append(event)
        
        task.status = TaskStatus.FAILED
        tasks[task.id] = task

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="localhost", port=5172, reload=True)
