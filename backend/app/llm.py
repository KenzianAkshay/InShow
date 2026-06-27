import json
from abc import ABC, abstractmethod
from typing import Callable


class LLMProvider(ABC):
    """Provider-agnostic chat interface. Implementations are selected per agent
    from its stored model_provider; API keys come from the environment."""

    @abstractmethod
    def complete(self, system: str, messages: list[dict]) -> str:
        ...

    def complete_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        dispatch: Callable[[str, dict], dict],
        max_rounds: int = 6,
    ) -> str:
        """Run an agentic tool-use loop, letting the model call `tools` (each
        executed by `dispatch`) until it produces a final answer. Default
        implementation ignores tools (used by test doubles); real providers
        override it."""
        return self.complete(system, messages)


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str, api_key: str | None = None):
        self.model = model or "claude-opus-4-8"
        self.api_key = api_key

    def complete(self, system: str, messages: list[dict]) -> str:
        import anthropic

        # api_key=None lets the SDK fall back to ANTHROPIC_API_KEY.
        response = anthropic.Anthropic(api_key=self.api_key or None).messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=messages,
        )
        return "".join(b.text for b in response.content if b.type == "text")

    def complete_with_tools(self, system, messages, tools, dispatch, max_rounds=6):
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key or None)
        atools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
        convo: list[dict] = list(messages)
        for _ in range(max_rounds):
            resp = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                tools=atools,
                messages=convo,
            )
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text")
            convo.append(
                {"role": "assistant", "content": [b.model_dump() for b in resp.content]}
            )
            results = [
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(dispatch(b.name, b.input)),
                }
                for b in resp.content
                if b.type == "tool_use"
            ]
            convo.append({"role": "user", "content": results})
        # Out of rounds: ask for a final answer without tools.
        resp = client.messages.create(
            model=self.model, max_tokens=2048, system=system, messages=convo
        )
        return "".join(b.text for b in resp.content if b.type == "text")


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str | None = None):
        self.model = model or "gpt-4o"
        self.api_key = api_key

    def complete(self, system: str, messages: list[dict]) -> str:
        from openai import OpenAI

        response = OpenAI(api_key=self.api_key or None).chat.completions.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""

    def complete_with_tools(self, system, messages, tools, dispatch, max_rounds=6):
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key or None)
        otools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]
        convo: list[dict] = [{"role": "system", "content": system}, *messages]
        for _ in range(max_rounds):
            resp = client.chat.completions.create(
                model=self.model, max_tokens=2048, messages=convo, tools=otools
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            convo.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(dispatch(tc.function.name, args)),
                    }
                )
        resp = client.chat.completions.create(
            model=self.model, max_tokens=2048, messages=convo
        )
        return resp.choices[0].message.content or ""


def get_provider(
    provider: str | None, model: str | None, api_key: str | None = None
) -> LLMProvider:
    if provider == "openai":
        return OpenAIProvider(model or "gpt-4o", api_key)
    return ClaudeProvider(model or "claude-opus-4-8", api_key)
