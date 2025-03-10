from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import uuid
import json
from typing import Dict
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

# In-memory storage (note: this will reset on each function invocation)
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
            content={"error": "Error rendering index page"}
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
        
        # Process task immediately in serverless environment
        try:
            agent = ToolCallAgent()
            task.status = TaskStatus.RUNNING
            
            result = await agent.run(prompt)
            
            task.status = TaskStatus.COMPLETED
            return {
                "id": task_id,
                "status": TaskStatus.COMPLETED,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Task processing error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "id": task_id,
                    "status": TaskStatus.FAILED,
                    "error": "Task processing failed"
                }
            )
            
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

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="localhost", port=5172, reload=True)
