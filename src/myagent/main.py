'''
Author: TonyInBeijing yuehaowei1126@gmail.com
LastEditors: TonyInBeijing yuehaowei1126@gmail.com
Description: 
Date: 2026-10-26 23:08:30
LastEditTime: 2026-10-26 23:14:01
FilePath: /MyAgent/src/myagent/main.py

'''
import uvicorn
from fastapi import FastAPI

from myagent import __version__
from myagent.api.routes import router


def create_app() -> FastAPI:
    application = FastAPI(
        title="MyAgent",
        version=__version__,
        description="MyAgent HTTP API",
    )
    application.include_router(router, prefix="/api/v1")
    return application


app = create_app()


def run() -> None:
    uvicorn.run("myagent.main:app", host="0.0.0.0", port=8000, reload=True)
