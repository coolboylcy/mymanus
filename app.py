from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API settings
os.environ.setdefault('OPENAI_API_KEY', 'sk-b225609809eb45da981394d494dafe3d')
os.environ.setdefault('OPENAI_API_BASE', 'https://api.deepseek.com/v1')

from app.agent import ToolCallAgent
from app.logger import logger
from app.schema import TaskStatus

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "API is running"}

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
        
        # Process task immediately
        try:
            agent = ToolCallAgent()
            result = await agent.run(prompt)
            
            return {
                "status": "success",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Task processing error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": str(e)
                }
            )
            
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}
