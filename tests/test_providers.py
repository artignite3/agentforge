import json
from pathlib import Path

import httpx
import pytest

from agentforge.providers import OUTPUT_LIMIT, HTTPProvider, ProviderError


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient

    def client(**kwargs):
        return original(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemini-2.5-flash"])
async def test_gemini_model_contract_and_thinking_token_accounting(settings, monkeypatch, model):
    settings.gemini_model = model
    settings.gemini_key = settings.api_key
    action = json.dumps(
        {"operation": "finish", "path": "", "content": "", "explanation": "Verified tests."}
    )
    rest_enums = json.loads(
        Path(__file__).with_name("fixtures").joinpath("gemini_rest_enums.json").read_text()
    )

    def handler(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.url.path == f"/v1beta/models/{model}:generateContent"
        assert not request.url.query
        assert request.headers["x-goog-api-key"] == settings.api_key.get_secret_value()
        config = json.loads(request.content)["generationConfig"]
        assert config["maxOutputTokens"] == OUTPUT_LIMIT
        if model.startswith("gemini-3"):
            assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}
            assert (
                config["thinkingConfig"]["thinkingLevel"]
                in rest_enums["ThinkingConfig"]["thinkingLevel"]
            )
            output = config["responseFormat"]["text"]
            assert output["mimeType"] == "APPLICATION_JSON"
            assert output["mimeType"] in rest_enums["TextResponseFormat"]["mimeType"]
            schema = output["schema"]
            assert "responseJsonSchema" not in config
        else:
            assert config["thinkingConfig"] == {"thinkingBudget": 0}
            assert config["responseMimeType"] == "application/json"
            schema = config["responseJsonSchema"]
            assert "responseFormat" not in config
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"operation", "path", "content", "explanation"}
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "Not an action; ignore this summary."},
                                {"text": action[:35]},
                                {"text": action[35:]},
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 17,
                    "thoughtsTokenCount": 50,
                    "totalTokenCount": 77,
                },
            },
        )

    install_transport(monkeypatch, handler)
    generation = await HTTPProvider(settings, "gemini").generate("Repair the fixture.", {})
    assert generation.action.operation == "finish"
    assert generation.input_tokens == 10
    assert generation.output_tokens == 67


@pytest.mark.parametrize(
    "status, kind, retryable",
    [
        (400, "ProviderHTTPError400", False),
        (404, "ProviderHTTPError404", False),
        (429, "RateLimited", True),
        (503, "ProviderHTTPError503", True),
    ],
)
async def test_upstream_http_failures_preserve_status_without_error_body(
    settings, monkeypatch, status, kind, retryable
):
    settings.gemini_key = settings.api_key
    secret = settings.api_key.get_secret_value()
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(status, json={"error": {"message": secret}}),
    )
    with pytest.raises(ProviderError) as error:
        await HTTPProvider(settings, "gemini").generate("Repair the fixture.", {})
    assert error.value.kind == kind
    assert error.value.retryable is retryable
    assert secret not in str(error.value)


async def test_gemini_rejects_thought_only_response(settings, monkeypatch):
    settings.gemini_key = settings.api_key
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"thought": True, "text": "reasoning"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 20},
            },
        ),
    )
    with pytest.raises(ProviderError, match="MalformedModelResponse"):
        await HTTPProvider(settings, "gemini").generate("Repair the fixture.", {})
