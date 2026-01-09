from pydantic import BaseModel

class ProblemDetails(BaseModel):
    status: int
    code: str
    message: str
    request_id: str


def problem(*, status: int, code: str, message: str, request_id: str) -> ProblemDetails:
    return ProblemDetails(status=status, code=code, message=message, request_id=request_id)