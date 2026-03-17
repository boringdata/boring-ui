import os
import time

from fastapi import FastAPI, Request, WebSocket
from starlette.responses import StreamingResponse
import uvicorn


INSTANCE = f"{time.time_ns()}-{os.getpid()}"
app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ping")
async def ping(request: Request):
    return {
        "greeting": "hello",
        "user": request.headers.get("x-boring-user-id"),
        "workspace": request.headers.get("x-boring-workspace-id"),
        "auth": request.headers.get("x-boring-auth"),
        "instance": INSTANCE,
    }


@app.get("/events")
async def events():
    async def stream():
        yield "event: ping\n"
        yield "data: hello\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.websocket("/ws")
async def ws_echo(websocket: WebSocket):
    await websocket.accept()
    while True:
        message = await websocket.receive_text()
        await websocket.send_text(message)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["PORT"]), log_level="warning")
