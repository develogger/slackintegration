import os
import secrets
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Slack GET Bridge",
    version="1.0.0",
    description="A tiny GET-only bridge that forwards an allow-listed message to Slack.",
)


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _allowed_channels() -> set[str]:
    channels = {
        x.strip()
        for x in os.getenv("SLACK_ALLOWED_CHANNELS", "").split(",")
        if x.strip()
    }

    default_channel = os.getenv("SLACK_DEFAULT_CHANNEL", "").strip()
    if default_channel:
        channels.add(default_channel)

    return channels


@app.middleware("http")
async def no_store_for_actions(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/slack/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/api")
async def root():
    return {
        "ok": True,
        "service": "slack-get-bridge",
        "endpoints": ["/api/health", "/api/slack/send"],
    }


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "slack-get-bridge"}


@app.get("/api/slack/send")
async def slack_send(
    token: str = Query(..., min_length=16, description="Bridge token, NOT your Slack token"),
    message: str = Query(..., min_length=1, max_length=3000),
    channel: Optional[str] = Query(
        default=None,
        description="Slack channel ID. If omitted, SLACK_DEFAULT_CHANNEL is used.",
    ),
    preview: bool = Query(
        default=False,
        description="If true, validate the request but do not send to Slack.",
    ),
):
    bridge_token = _env("BRIDGE_TOKEN")
    if not secrets.compare_digest(token, bridge_token):
        raise HTTPException(status_code=401, detail="Invalid bridge token")

    target = (channel or os.getenv("SLACK_DEFAULT_CHANNEL", "")).strip()
    if not target:
        raise HTTPException(
            status_code=500,
            detail="No target channel configured. Set SLACK_DEFAULT_CHANNEL.",
        )

    allowed = _allowed_channels()
    if not allowed:
        raise HTTPException(
            status_code=500,
            detail="No Slack channels are allow-listed.",
        )

    if target not in allowed:
        raise HTTPException(status_code=403, detail="Channel is not allow-listed")

    blocked_mentions = ("<!channel>", "<!here>", "<!everyone>")
    if any(m in message for m in blocked_mentions):
        raise HTTPException(
            status_code=400,
            detail="Broadcast mentions are disabled by this bridge.",
        )

    if preview:
        return {
            "ok": True,
            "preview": True,
            "channel": target,
            "message": message,
        }

    slack_token = _env("SLACK_BOT_TOKEN")
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        post_resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json={
                "channel": target,
                "text": message,
                "unfurl_links": False,
                "unfurl_media": False,
            },
        )

        try:
            post_data = post_resp.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail=f"Slack returned a non-JSON response ({post_resp.status_code})",
            )

        if post_resp.status_code >= 400 or not post_data.get("ok"):
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Slack rejected the request",
                    "slack_error": post_data.get("error", "unknown_error"),
                },
            )

        permalink = None
        ts = post_data.get("ts")
        if ts:
            link_resp = await client.get(
                "https://slack.com/api/chat.getPermalink",
                headers={"Authorization": f"Bearer {slack_token}"},
                params={"channel": target, "message_ts": ts},
            )
            try:
                link_data = link_resp.json()
                if link_data.get("ok"):
                    permalink = link_data.get("permalink")
            except ValueError:
                pass

    return JSONResponse(
        {
            "ok": True,
            "channel": target,
            "ts": ts,
            "permalink": permalink,
        }
    )
