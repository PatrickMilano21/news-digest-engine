import uuid
from fastapi import Request


async def request_id_middleware(request: Request, call_next):
    #1. Generate a unique recent ID
    request_id = uuid.uuid4().hex

    #2. Attach it to the request state (lives for this request only)
    request.state.request_id = request_id

    #3Let the request continue through the rest of the app
    response = await call_next(request)

    #4. Add the request ID to the response headers
    response.headers['X-Request-ID'] = request_id

    return response