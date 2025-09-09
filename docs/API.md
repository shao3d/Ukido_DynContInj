# API Documentation

## Base URL

```
http://localhost:8000
```

For production deployment, replace with your actual domain.

## Authentication

Currently, the API does not require authentication. Each request must include a `user_id` to track conversation history.

## Endpoints

### 1. Chat Endpoint

Send a message to the AI assistant and receive a response.

#### Request

```http
POST /chat
Content-Type: application/json
```

#### Request Body

```json
{
  "user_id": "string",  // Required, unique identifier for the user
  "message": "string"   // Required, user's message (1-1000 characters)
}
```

#### Response

```json
{
  "response": "string",           // AI assistant's response
  "intent": "string",             // Message intent: "success", "offtopic", "need_simplification"
  "user_signal": "string",        // User's emotional state: "exploring_only", "anxiety_about_child", "price_sensitive", "ready_to_buy"
  "relevant_documents": ["..."],  // List of documents used for response
  "confidence": 0.95,             // Confidence score (0-1)
  "decomposed_questions": ["..."], // Decomposed questions if complex query
  "fuzzy_matched": false,         // Whether fuzzy matching was used
  "social": null,                 // Social context if detected
  "detected_language": "ru",      // Detected language: "ru", "uk", "en"
  "metadata": {                   // Additional metadata
    "cta_added": false,
    "cta_blocked": true,
    "block_reason": "rate_limit",
    "humor_generated": false
  }
}
```

#### Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "parent_123",
    "message": "Сколько стоят ваши курсы?"
  }'
```

### 2. Streaming Chat Endpoint

Get real-time streaming responses using Server-Sent Events (SSE).

#### Request

```http
GET /chat/stream?user_id={user_id}&message={message}
```

#### Query Parameters

- `user_id` (required): Unique identifier for the user
- `message` (required): User's message (URL-encoded)

#### Response

Server-Sent Events stream with the following event types:

```
event: start
data: {"intent": "success", "user_signal": "exploring_only"}

event: token
data: {"token": "Наши"}

event: token
data: {"token": " курсы"}

event: done
data: {"message": "Stream completed"}
```

#### Example (JavaScript)

```javascript
const eventSource = new EventSource(
  `/chat/stream?user_id=user123&message=${encodeURIComponent("Расскажите о курсах")}`
);

eventSource.addEventListener('token', (event) => {
  const data = JSON.parse(event.data);
  console.log('Received token:', data.token);
});

eventSource.addEventListener('done', (event) => {
  eventSource.close();
});
```

### 3. Health Check

Check if the server is running and healthy.

#### Request

```http
GET /health
```

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2025-01-13T12:34:56.789Z"
}
```

### 4. Metrics

Get system metrics and statistics.

#### Request

```http
GET /metrics
```

#### Response

```json
{
  "uptime_seconds": 3600,
  "total_requests": 150,
  "avg_latency": 2.3,
  "signal_distribution": {
    "exploring_only": 45,
    "price_sensitive": 30,
    "anxiety_about_child": 20,
    "ready_to_buy": 5
  },
  "cache_stats": {
    "hit_rate": 0.85,
    "size": 234
  }
}
```

### 5. Web Interface

Access the interactive chat interface.

#### Request

```http
GET /
```

Opens the web-based chat interface with real-time streaming support.

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

Error response format:

```json
{
  "detail": "Error description"
}
```

## Rate Limiting

Currently, there are no hard rate limits, but the system includes:
- Humor generation limited to 5 per hour per user
- CTA (Call-to-action) rate limiting: 1 per 2 messages minimum

## Language Support

The API automatically detects the language of the input message and responds in the same language. Supported languages:
- Russian (`ru`) - Primary language
- Ukrainian (`uk`) - Full support with real-time translation
- English (`en`) - Full support with real-time translation

## User Context

The system maintains conversation history for each `user_id`:
- Last 10 messages are kept in memory
- User emotional state is tracked across messages
- Conversation context persists for up to 7 days (with persistence enabled)

## WebSocket Support (Future)

WebSocket support for real-time bidirectional communication is planned for future releases.

## SDK Examples

### Python

```python
import httpx

def chat_with_ukido(user_id: str, message: str):
    response = httpx.post(
        "http://localhost:8000/chat",
        json={"user_id": user_id, "message": message}
    )
    return response.json()

# Usage
result = chat_with_ukido("parent_456", "Какие курсы есть для детей 10 лет?")
print(result["response"])
```

### JavaScript/Node.js

```javascript
async function chatWithUkido(userId, message) {
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, message: message })
  });
  return await response.json();
}

// Usage
chatWithUkido('parent_789', 'Расскажите о преподавателях')
  .then(result => console.log(result.response));
```

## Testing

Use the included sandbox tool for testing:

```bash
# Interactive mode
python tests/sandbox/http_sandbox.py -i

# Send single message
python tests/sandbox/http_sandbox.py -m "Привет!"

# Run test dialogue
python tests/sandbox/http_sandbox.py dialog_v2_1
```