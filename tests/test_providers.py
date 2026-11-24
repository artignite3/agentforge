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


def openai_response(text, **extra):
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
        "usage": {"input_tokens": 12, "output_tokens": 30},
        **extra,
    }


async def test_openai_responses_contract_and_usage(settings, monkeypatch):
    settings.openai_key = settings.api_key
    action = json.dumps(
        {"operation": "run_tests", "path": "", "content": "", "explanation": "Reproduce."}
    )

    def handler(request):
        assert request.url.host == "api.openai.com"
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == "Bearer " + settings.api_key.get_secret_value()
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["max_output_tokens"] == OUTPUT_LIMIT
        fmt = body["text"]["format"]
        assert fmt["type"] == "json_schema" and fmt["strict"] is True
        assert fmt["schema"]["additionalProperties"] is False
        assert set(fmt["schema"]["required"]) == set(fmt["schema"]["properties"])
        return httpx.Response(200, json=openai_response(action))

    install_transport(monkeypatch, handler)
    generation = await HTTPProvider(settings, "openai").generate("Repair the fixture.", {})
    assert generation.action.operation == "run_tests"
    assert (generation.input_tokens, generation.output_tokens) == (12, 30)


@pytest.mark.parametrize(
    "payload, kind, retryable",
    [
        (
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
            "ModelRefusal",
            False,
        ),
        (
            openai_response('{"operation": "fin', status="incomplete"),
            "IncompleteModelResponse",
            True,
        ),
        (openai_response('{"operation": "delete_everything"}'), "MalformedModelResponse", True),
    ],
)
async def test_openai_refusal_incomplete_and_invalid_actions(
    settings, monkeypatch, payload, kind, retryable
):
    settings.openai_key = settings.api_key
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(ProviderError) as error:
        await HTTPProvider(settings, "openai").generate("Repair the fixture.", {})
    assert (error.value.kind, error.value.retryable) == (kind, retryable)


@pytest.mark.parametrize(
    "header, expected",
    [("7", 7.0), ("Wed, 21 Oct 2026 07:28:00 GMT", None), (None, None), ("-1", None)],
)
async def test_rate_limit_retry_after_hint(settings, monkeypatch, header, expected):
    settings.gemini_key = settings.api_key
    headers = {"retry-after": header} if header else {}
    install_transport(monkeypatch, lambda request: httpx.Response(429, headers=headers))
    with pytest.raises(ProviderError) as error:
        await HTTPProvider(settings, "gemini").generate("Repair the fixture.", {})
    assert error.value.kind == "RateLimited"
    assert error.value.retry_after == expected
