from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Provider-agnostic chat interface. Implementations are selected per agent
    from its stored model_provider; API keys come from the environment."""

    @abstractmethod
    def complete(self, system: str, messages: list[dict]) -> str:
        ...


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


def get_provider(
    provider: str | None, model: str | None, api_key: str | None = None
) -> LLMProvider:
    if provider == "openai":
        return OpenAIProvider(model or "gpt-4o", api_key)
    return ClaudeProvider(model or "claude-opus-4-8", api_key)
