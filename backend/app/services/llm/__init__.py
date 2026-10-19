"""Small provider-agnostic stream interface; provider exceptions never escape."""

from dataclasses import dataclass
from typing import AsyncIterator, Literal, Protocol


class LLMError(Exception):
    def __init__(self, message="The assistant is unavailable. Please try again shortly."):
        super().__init__(message)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class Event:
    kind: Literal["token", "tool"]
    text: str = ""
    call: ToolCall | None = None


class LLMClient(Protocol):
    def stream(
        self, *, system: str, messages: list, tools: list, force_final: bool = False
    ) -> AsyncIterator[Event]: ...

    async def categorize(self, merchant: str) -> str | None: ...


def get_client():
    from app.config import get_settings
    from app.services.llm.fake import FakeLLM

    cfg = get_settings()
    if cfg.llm_provider == "fake":
        return FakeLLM()
    from app.services.llm.anthropic import AnthropicClient

    return AnthropicClient(cfg)
