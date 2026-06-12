import pytest
from unittest.mock import AsyncMock, patch
import json
import asyncio

from src.config import PromptConfig
from src.classifier import classify_email, get_mock_response

def test_mock_response_v1_rules():
    # Billing matching
    r1 = get_mock_response("Please refund my charge", "1.0.0")
    assert r1["category"] == "billing"

    # Technical matching
    r2 = get_mock_response("I get a 500 error when logging in", "1.0.0")
    assert r2["category"] == "technical"

    # Account matching
    r3 = get_mock_response("I want to delete my account", "1.0.0")
    assert r3["category"] == "account"

    # General matching (fallback)
    r4 = get_mock_response("Hello, hope you are well", "1.0.0")
    assert r4["category"] == "general"

def test_mock_response_v2_regressions():
    # Sarcasm misclassification regression
    r1 = get_mock_response("I love getting double billed", "2.0.0")
    assert r1["category"] == "general"
    assert "happy" in r1["summary"]

    # Double intent regression
    r2 = get_mock_response("I want to login and check my charge", "2.0.0")
    assert r2["category"] == "technical"

    # Typo regression
    r3 = get_mock_response("I found a typo or a glitchy field", "2.0.0")
    assert r3["category"] == "general"

    # V2 summary length checks
    r4 = get_mock_response("simple message", "2.0.0")
    assert "contacting support" in r4["summary"]

@pytest.mark.asyncio
async def test_classify_email_mock_path(mock_prompt_config_v1):
    # Tests that when IS_MOCK is True, it resolves to mock response
    with patch("src.classifier.IS_MOCK", True):
        res = await classify_email("I need a refund", mock_prompt_config_v1)
        assert res["category"] == "billing"
        assert res["error"] is None
        assert res["latency"] > 0

@pytest.mark.asyncio
@patch("src.classifier.IS_MOCK", False)
async def test_classify_email_live_success(mock_prompt_config_v1):
    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content='{"category": "billing", "summary": "Refund request processed."}'))
    ]
    mock_resp.usage = AsyncMock(prompt_tokens=22, completion_tokens=11)
    
    with patch("litellm.acompletion", return_value=mock_resp) as mock_complete:
        res = await classify_email("Refund double billing please", mock_prompt_config_v1)
        assert res["category"] == "billing"
        assert res["summary"] == "Refund request processed."
        assert res["input_tokens"] == 22
        assert res["output_tokens"] == 11
        assert res["error"] is None
        mock_complete.assert_called_once()

@pytest.mark.asyncio
@patch("src.classifier.IS_MOCK", False)
async def test_classify_email_live_markdown_stripping(mock_prompt_config_v1):
    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content='```json\n{"category": "account", "summary": "GDPR delete account request."}\n```'))
    ]
    mock_resp.usage = None # Test when usage stats are missing from api return
    
    with patch("litellm.acompletion", return_value=mock_resp):
        res = await classify_email("Delete my account GDPR", mock_prompt_config_v1)
        assert res["category"] == "account"
        assert res["summary"] == "GDPR delete account request."
        assert res["input_tokens"] == 0
        assert res["output_tokens"] == 0
        assert res["error"] is None

@pytest.mark.asyncio
@patch("src.classifier.IS_MOCK", False)
async def test_classify_email_live_exception(mock_prompt_config_v1):
    with patch("litellm.acompletion", side_effect=Exception("Connection timed out")):
        res = await classify_email("Some test input", mock_prompt_config_v1)
        assert res["category"] == "general"
        assert res["input_tokens"] == 0
        assert res["error"] == "Connection timed out"
