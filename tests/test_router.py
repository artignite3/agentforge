import pytest

from agentforge.domain import Agent
from agentforge.providers import ProviderError, Router


def test_router_cost_fallback_and_explicit_preference(settings):
    settings.openai_key = settings.api_key
    settings.gemini_key = settings.api_key
    settings.gemini_input_rate = 0.5
    settings.gemini_output_rate = 1.0
    router = Router(settings)
    agent = Agent(provider="auto")
    assert router.select(agent, "hello", 1000000, []).provider == "gemini"
    assert router.select(agent, "hello", 1000000, ["gemini"]).provider == "openai"
    assert (
        router.select(Agent(provider="gemini"), "hello", 1000000, ["gemini"]).provider == "gemini"
    )
    with pytest.raises(ProviderError, match="NoAffordableProvider"):
        router.select(agent, "hello", 1, [])


def test_live_never_falls_back_to_demo(settings):
    with pytest.raises(ProviderError, match="ProviderNotConfigured"):
        Router(settings).select(Agent(provider="auto"), "hello", 1000000, [])
