from pydantic import BaseModel


class AgentRequest(BaseModel):
    message: str
    session_id: str


class AgentResponse(BaseModel):
    type: str
    content: str | None = None
    tool: str | None = None
    tool_calls: list[str] | None = None
