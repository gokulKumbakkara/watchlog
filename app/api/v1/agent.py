import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.db.models import User
from app.schemas.agent import AgentRequest
from app.services.auth import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/chat")
@limiter.limit(settings.AGENT_RATE_LIMIT)
async def agent_chat(
    request: Request,
    body: AgentRequest,
    current_user: User = Depends(get_current_user),
):
    return StreamingResponse(
        _stream_agent(request, body, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_agent(request: Request, body: AgentRequest, current_user: User):
    from app.db.session import AsyncSessionLocal
    from app.services.crud import get_recent_messages, save_message
    from app.agent.agent import build_agent, format_chat_history
    from app.agent.tools import set_user_context

    redis = request.app.state.redis
    chroma = request.app.state.chroma
    session_id = body.session_id
    user_message = body.message

    # Scope all tool DB calls to this user
    set_user_context(current_user.id)

    tool_calls_made: list[str] = []
    full_response = ""
    _buffer = ""
    _in_final_answer = False
    FINAL_ANSWER_PREFIX = "Final Answer:"

    try:
        async with AsyncSessionLocal() as db:
            history = await get_recent_messages(db, session_id, limit=10)
            await save_message(db, session_id, "user", user_message, user_id=current_user.id)
            await db.commit()

        chat_history_str = format_chat_history(history)
        executor = build_agent(AsyncSessionLocal, redis, chroma)

        async for event in executor.astream_events(
            {"input": user_message, "chat_history": chat_history_str},
            version="v2",
        ):
            event_type = event.get("event", "")
            event_data = event.get("data", {})

            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content

                    if _in_final_answer:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
                    else:
                        _buffer += chunk.content
                        if FINAL_ANSWER_PREFIX in _buffer:
                            _in_final_answer = True
                            after = _buffer.split(FINAL_ANSWER_PREFIX, 1)[1].lstrip()
                            if after:
                                yield f"data: {json.dumps({'type': 'token', 'content': after})}\n\n"
                            _buffer = ""

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "unknown_tool")
                if tool_name != "web_search_fallback":
                    tool_calls_made.append(tool_name)
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name})}\n\n"

        if FINAL_ANSWER_PREFIX in full_response:
            saved_response = full_response.split(FINAL_ANSWER_PREFIX, 1)[1].strip()
        else:
            saved_response = full_response or "[agent response]"

        async with AsyncSessionLocal() as db:
            await save_message(
                db, session_id, "assistant", saved_response,
                user_id=current_user.id,
                tool_calls=tool_calls_made,
            )
            await db.commit()

        yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls_made})}\n\n"

    except Exception as e:
        err_str = str(e)
        logger.exception(f"Agent error for session={session_id}: {e}")
        if "429" in err_str or "rate_limit" in err_str.lower() or "Rate limit" in err_str:
            msg = "Limit reached"
        else:
            msg = "Something went wrong. Please try again."
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"
