from pydantic import BaseModel


class ProblemDetails(BaseModel):
    status: int
    code: str
    message: str
    request_id: str
    run_id: str | None = None


def problem(*, status: int, code: str, message: str, request_id: str, run_id: str | None = None) -> ProblemDetails:
    return ProblemDetails(status=status, code=code, message=message, request_id=request_id, run_id=run_id)
