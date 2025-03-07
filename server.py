from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
import uuid
import json
from queue import Queue
from threading import Lock

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store client connections and pending requests
client_connections = {}
pending_requests = {}
request_lock = Lock()

# Queue for each client to store pending requests
request_queues = {}


async def event_generator(client_id):
    """Generate SSE events for a specific client."""
    if client_id not in request_queues:
        request_queues[client_id] = Queue()

    while True:
        # If there are pending requests for this client, send them
        if not request_queues[client_id].empty():
            with request_lock:
                request = request_queues[client_id].get()

            # Format as SSE event
            yield f"data: {json.dumps(request)}\n\n"

        # Wait a bit before checking again
        await asyncio.sleep(0.1)


@app.get("/ping")
async def ping():
    return "pong"


@app.get("/api/events/{client_id}")
async def events(client_id: str):
    """Endpoint for SSE connection from client."""
    client_connections[client_id] = True
    return EventSourceResponse(event_generator(client_id))


@app.post("/api/response")
async def receive_response(request: Request):
    """Endpoint for client to respond to AI requests."""
    data = await request.json()
    request_id = data.get("id")

    with request_lock:
        if request_id in pending_requests:
            # Resolve the waiting request
            pending_requests[request_id]["response"] = data.get("data")
            pending_requests[request_id]["event"].set()

    return {"status": "ok"}


@app.post("/api/register")
async def register_client(request: Request):
    """Register a new client and return a client ID."""
    client_id = str(uuid.uuid4())
    request_queues[client_id] = Queue()
    return {"client_id": client_id}


# Function to be used by your LangChain tools
async def request_client_data(client_id, request_type, **kwargs):
    """Request data from a specific client."""
    if client_id not in client_connections:
        return None

    request_id = str(uuid.uuid4())
    event = asyncio.Event()

    with request_lock:
        pending_requests[request_id] = {"event": event, "response": None}

    # Create request object
    request = {"id": request_id, "type": request_type, **kwargs}

    # Add to client's queue
    request_queues[client_id].put(request)

    # Wait for response with timeout
    try:
        await asyncio.wait_for(event.wait(), timeout=30.0)
        with request_lock:
            response = pending_requests[request_id]["response"]
            del pending_requests[request_id]
        return response
    except asyncio.TimeoutError:
        with request_lock:
            if request_id in pending_requests:
                del pending_requests[request_id]
        return None


# Example LangChain tool wrapper
from langchain.tools import Tool


def create_screen_capture_tool(client_id):
    """Create a LangChain tool for requesting screen captures."""

    async def get_screen_capture():
        screen_data = await request_client_data(
            client_id, "screenCapture", region="full"
        )
        # Process screen_data as needed
        return screen_data

    return Tool(
        name="screen_capture",
        func=get_screen_capture,
        description="Captures the current screen content",
    )


import uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
