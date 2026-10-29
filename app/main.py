# app/main.py — Lab 5 example: a one-page AI summariser.
#
# The browser talks only to this server; this server talks to the AI provider
# (app/ai.py). The key is read from the environment and never leaves the server.
# No database: the point of this example is the AI call, the key and the failure path.
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app import ai

APP_VERSION = "1.0.0"
FRIENDLY = "The AI feature is unavailable right now. Please try again in a minute."
PAGE = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")

app = FastAPI(title="ai-summariser")


class SummariseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)  # empty or huge text gets 422


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE


@app.get("/health")
def health():
    # Fast, no AI call. Render's health check path points here.
    return {"status": "ok", "version": APP_VERSION}


@app.post("/api/summarise")
def summarise(req: SummariseRequest):
    try:
        summary = ai.summarize_safe(req.text)
    except ai.AIUnavailable as err:
        print("ai failed:", err.reason)  # the reason goes to the logs, never the key
        return JSONResponse(status_code=503, content={"summary": None, "message": FRIENDLY})
    return {"summary": summary}
