# Ukido API

Local base URL: `http://localhost:8000`. Production base URL:
`https://ukido.beyondhorizon.dev`.

The public chat and trial endpoints do not use API authentication. `user_id`
identifies conversation state; it is not an authentication credential.
Administrative endpoints require `X-Admin-Token` when `ADMIN_API_TOKEN` is
configured and return `404` when it is not configured.

Interactive OpenAPI documentation is available at `/docs`.

## Chat

### `POST /chat`

```json
{
  "user_id": "parent_123",
  "message": "Какие курсы подходят ребёнку 10 лет?"
}
```

`user_id` must contain 1–50 ASCII letters, digits, `_` or `-`. `message` is
trimmed and must contain 1–1000 characters.

The response contains the final text plus routing information:

```json
{
  "response": "...",
  "relevant_documents": ["courses_detailed.md"],
  "intent": "success",
  "confidence": 1.0,
  "decomposed_questions": [],
  "fuzzy_matched": false,
  "social": null,
  "user_signal": "exploring_only",
  "metadata": {
    "cta_added": false,
    "humor_generated": false
  },
  "detected_language": "ru"
}
```

Fields may vary by route; optional fields can be `null`. Supported detected
languages are `ru`, `uk` and `en`. For non-Russian answers
`metadata.translated_to` records the target language (`uk` or `en`); translation
metadata is absent when no translation was needed.

### `GET /chat/stream`

Query parameters are the same `user_id` and `message`. The endpoint returns
Server-Sent Events in this order:

```text
event: metadata
data: {"intent":"success","user_signal":"exploring_only","humor_generated":false,"detected_language":"ru"}

event: message
data: Ответ

event: done
data: completed
```

There can be many `message` events. An SSE comment heartbeat is emitted every
15 seconds by the server. Processing failures produce an `error` event.

## Trial signup

### `POST /trial-signup`

```json
{
  "firstName": "Анна",
  "lastName": "Иванова",
  "email": "anna@example.com",
  "phone": "+380 50 123 45 67",
  "language": "uk"
}
```

`phone` is optional. `language` is optional and accepts `ru`, `uk` or `en`;
the default is `ru`. A successful response has `success` and a localized
`message`. The response never reveals whether the contact was created or
updated, and HubSpot contact IDs are not exposed.

## System endpoints

- `GET /health` — public liveness response with `status` and application
  `version`.
- `GET /api-info` — public service name and application version.
- `GET /metrics` — runtime, signal, humour and persistence metrics;
  administrative access only.
- `POST /clear_history/{user_id}` — clears one user's conversation history;
  administrative access only.
- `GET /` — static web chat. It is mounted last so API routes take priority.

## Errors and limits

Validation errors return HTTP `422`; rate-limit violations return HTTP `429`
(with a `Retry-After` header); unexpected processing errors return HTTP `500`.
Request limits apply in process memory to `/chat`, `/chat/stream` and
`/trial-signup`: each chat user is limited to 10 requests per minute and 100 per
calendar day, each client IP (last `X-Forwarded-For` hop set by the proxy) to
30 per minute and 300 per day, all chat requests to a global 600 per minute,
and trial signups to 5 per minute and 20 per day per IP. These limits reset
when the process restarts and are not shared between multiple instances.
