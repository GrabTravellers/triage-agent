#!/usr/bin/env python3
"""
Script to run the FastAPI application with uvicorn
"""

import uvicorn

from fastapi_app import app

if __name__ == "__main__":
    print("Starting FastAPI application...")
    print("Access the API at: http://localhost:8000")
    print("Interactive API docs at: http://localhost:8000/docs")
    print("Alternative docs at: http://localhost:8000/redoc")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info",
    )
