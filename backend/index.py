# from bs4 import BeautifulSoup
# import json
# import markdown
import time
# import os
import sys
import logging
import aiohttp
# import requests

from fastapi import FastAPI, Request, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware


from apps.openai.main import app as openai_app

from apps.web.main import app as webui_app

from pydantic import BaseModel
from typing import List


from utils.utils import get_admin_user

from config import (
    CONFIG_DATA,
    WEBUI_NAME,
    VERSION,
    CHANGELOG,
    STATIC_DIR,
    ENABLE_MODEL_FILTER,
    MODEL_FILTER_LIST,
    GLOBAL_LOG_LEVEL,
    SRC_LOG_LEVELS,
    WEBHOOK_URL,
    ENABLE_ADMIN_EXPORT,
)
from constants import ERROR_MESSAGES

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

print(f"""
  Open WebUI
  v{VERSION} - building the best open-source AI user interface.      
  https://github.com/open-webui/open-webui
""")

app = FastAPI()

app.state.ENABLE_MODEL_FILTER = ENABLE_MODEL_FILTER
app.state.MODEL_FILTER_LIST = MODEL_FILTER_LIST

app.state.WEBHOOK_URL = WEBHOOK_URL

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.middleware("http")
async def check_url(request: Request, call_next):
    start_time = int(time.time())
    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)

    return response


app.mount("/api/v1", webui_app)
app.mount("/openai/api", openai_app)

@app.get("/api/config")
async def get_app_config():
    # Checking and Handling the Absence of 'ui' in CONFIG_DATA

    default_locale = "en-US"
    if "ui" in CONFIG_DATA:
        default_locale = CONFIG_DATA["ui"].get("default_locale", "en-US")

    # The Rest of the Function Now Uses the Variables Defined Above
    return {
        "status": True,
        "name": WEBUI_NAME,
        "version": VERSION,
        "default_locale": default_locale,
        "images": False,
        "default_models": webui_app.state.DEFAULT_MODELS,
        "default_prompt_suggestions": webui_app.state.DEFAULT_PROMPT_SUGGESTIONS,
        "trusted_header_auth": bool(webui_app.state.AUTH_TRUSTED_EMAIL_HEADER),
        "admin_export_enabled": ENABLE_ADMIN_EXPORT,
    }


@app.get("/api/config/model/filter")
async def get_model_filter_config(user=Depends(get_admin_user)):
    return {
        "enabled": app.state.ENABLE_MODEL_FILTER,
        "models": app.state.MODEL_FILTER_LIST,
    }


class ModelFilterConfigForm(BaseModel):
    enabled: bool
    models: List[str]


@app.post("/api/config/model/filter")
async def update_model_filter_config(
    form_data: ModelFilterConfigForm, user=Depends(get_admin_user)
):
    app.state.ENABLE_MODEL_FILTER = form_data.enabled
    app.state.MODEL_FILTER_LIST = form_data.models

    # ollama_app.state.ENABLE_MODEL_FILTER = app.state.ENABLE_MODEL_FILTER
    # ollama_app.state.MODEL_FILTER_LIST = app.state.MODEL_FILTER_LIST

    openai_app.state.ENABLE_MODEL_FILTER = app.state.ENABLE_MODEL_FILTER
    openai_app.state.MODEL_FILTER_LIST = app.state.MODEL_FILTER_LIST

    # litellm_app.state.ENABLE_MODEL_FILTER = app.state.ENABLE_MODEL_FILTER
    # litellm_app.state.MODEL_FILTER_LIST = app.state.MODEL_FILTER_LIST

    return {
        "enabled": app.state.ENABLE_MODEL_FILTER,
        "models": app.state.MODEL_FILTER_LIST,
    }


@app.get("/api/webhook")
async def get_webhook_url(user=Depends(get_admin_user)):
    return {
        "url": app.state.WEBHOOK_URL,
    }


class UrlForm(BaseModel):
    url: str


@app.post("/api/webhook")
async def update_webhook_url(form_data: UrlForm, user=Depends(get_admin_user)):
    app.state.WEBHOOK_URL = form_data.url

    webui_app.state.WEBHOOK_URL = app.state.WEBHOOK_URL

    return {
        "url": app.state.WEBHOOK_URL,
    }


@app.get("/api/version")
async def get_app_config():
    return {
        "version": VERSION,
    }


@app.get("/api/changelog")
async def get_app_changelog():
    return {key: CHANGELOG[key] for idx, key in enumerate(CHANGELOG) if idx < 5}


@app.get("/api/version/updates")
async def get_app_latest_release_version():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/repos/open-webui/open-webui/releases/latest"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                latest_version = data["tag_name"]

                return {"current": VERSION, "latest": latest_version[1:]}
    except aiohttp.ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
        )


@app.get("/manifest.json")
async def get_manifest_json():
    return {
        "name": WEBUI_NAME,
        "short_name": WEBUI_NAME,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#343541",
        "theme_color": "#343541",
        "orientation": "portrait-primary",
        "icons": [{"src": "/favicon.png", "type": "image/png", "sizes": "844x884"}],
    }