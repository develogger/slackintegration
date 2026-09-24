# Slack GET Bridge for Vercel

A tiny FastAPI bridge designed for a client that can only open **GET URLs**.

Flow:

`GET URL -> this bridge -> Slack Web API -> JSON result`

The Slack bot token stays on the server and is never placed in the URL.

## Project structure

```text
slackintegration/
├── api/
│   └── index.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Slack setup

Create or use a Slack app with a bot token (`xoxb-...`).

For sending messages, the bot normally needs the `chat:write` scope and access to the target channel.

Use the Slack **channel ID**, not only the channel name.

## Deploy to Vercel

Import this GitHub repository into Vercel, then add these Environment Variables:

```text
BRIDGE_TOKEN
SLACK_BOT_TOKEN
SLACK_DEFAULT_CHANNEL
SLACK_ALLOWED_CHANNELS
```

Use a long random value for `BRIDGE_TOKEN`. It is a bridge password, not the Slack token.

## Health check

After deploy:

```text
https://YOUR-PROJECT.vercel.app/api/health
```

Expected:

```json
{"ok":true,"service":"slack-get-bridge"}
```

## Preview without sending

```text
https://YOUR-PROJECT.vercel.app/api/slack/send?token=YOUR_BRIDGE_TOKEN&message=hello&preview=true
```

## Send a real Slack message

```text
https://YOUR-PROJECT.vercel.app/api/slack/send?token=YOUR_BRIDGE_TOKEN&message=hello
```

To target another allow-listed channel:

```text
https://YOUR-PROJECT.vercel.app/api/slack/send?token=YOUR_BRIDGE_TOKEN&channel=C0123456789&message=hello
```

Always URL-encode the message.

A successful response looks roughly like:

```json
{
  "ok": true,
  "channel": "C0123456789",
  "ts": "1234567890.123456",
  "permalink": "https://..."
}
```

## Security notes

This project intentionally supports a side-effecting GET request because the intended client can only open URLs. That is not ideal HTTP semantics.

Protections included:

- The real Slack bot token never goes in the URL.
- Only allow-listed Slack channel IDs can be used.
- Broadcast mentions are blocked by default.
- Action responses are marked `no-store`.

However, `BRIDGE_TOKEN` does appear in the URL and may therefore appear in browser, proxy, or hosting logs. Treat it as a limited, rotatable action key:

- make it long and random;
- never reuse a password or Slack token;
- rotate it if it leaks;
- keep the Slack bot permissions minimal;
- keep the channel allow-list narrow.

For stronger security later, upgrade to short-lived signed action URLs or one-time action tokens.
