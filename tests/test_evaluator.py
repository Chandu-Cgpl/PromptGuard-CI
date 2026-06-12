import pytest
import os
import json
from unittest.mock import AsyncMock, patch
import asyncio

from src.config import PromptConfig, TestCase, TestResult
from src.evaluator import (
    get_mock_relevance,
    judge_summary_relevance,
    evaluate_single_case,
    run_evaluation_suite,
    diff_results,
    IS_MOCK
)

def test_get_mock_relevance():
    c_easy = TestCase(id="c1", input="in", expected_category="billing", expected_summary="ex", expected_difficulty="easy")
    c_med = TestCase(id="c2", input="in", expected_category="billing", expected_summary="ex", expected_difficulty="medium")
    c_hard = TestCase(id="c3", input="in", expected_category="billing", expected_summary="ex", expected_difficulty="hard")
    
    assert get_mock_relevance(c_easy, "1.0.0") == 5.0
    assert get_mock_relevance(c_med, "1.0.0") == 4.5
    assert get_mock_relevance(c_hard, "1.0.0") == 4.0

    assert get_mock_relevance(c_easy, "2.0.0") == 4.0
    assert get_mock_relevance(c_med, "2.0.0") == 3.0
    assert get_mock_relevance(c_hard, "2.0.0") == 2.0

@pytest.mark.asyncio
async def test_judge_summary_relevance_mock_path():
    with patch("src.evaluator.IS_MOCK", True):
        score, reason = await judge_summary_relevance("email", "ex", "act")
        assert score == 0.0
        assert "Mock mode" in reason

@pytest.mark.asyncio
@patch("src.evaluator.IS_MOCK", False)
async def test_judge_summary_relevance_live_success():
    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content='{"score": 4.5, "reason": "Very accurate summary."}'))
    ]
    with patch("litellm.acompletion", return_value=mock_resp):
        score, reason = await judge_summary_relevance("email", "ex", "act")
        assert score == 4.5
        assert reason == "Very accurate summary."

@pytest.mark.asyncio
@patch("src.evaluator.IS_MOCK", False)
async def test_judge_summary_relevance_live_error_stripping():
    # Test json parsing and markdown code wrapper stripping
    mock_resp = AsyncMock()
    mock_resp.choices = [
        AsyncMock(message=AsyncMock(content='```json\n{"score": 2.0, "reason": "Bad summary."}\n```'))
    ]
    with patch("litellm.acompletion", return_value=mock_resp):
        score, reason = await judge_summary_relevance("email", "ex", "act")
        assert score == 2.0
        assert reason == "Bad summary."

@pytest.mark.asyncio
@patch("src.evaluator.IS_MOCK", False)
async def test_judge_summary_relevance_live_exception():
    with patch("litellm.acompletion", side_effect=Exception("Timeout")):
        score, reason = await judge_summary_relevance("email", "ex", "act")
        assert score == 1.0
        assert "Error running LLM-as-judge" in reason

@pytest.mark.asyncio
async def test_evaluate_single_case(mock_prompt_config_v1):
    case = TestCase(id="c1", input="I need to cancel my billing subscription refund charge", expected_category="billing", expected_summary="ex")
    semaphore = asyncio.Semaphore(1)
    
    with patch("src.evaluator.IS_MOCK", True):
        res = await evaluate_single_case(case, mock_prompt_config_v1, semaphore)
        assert res.case_id == "c1"
        assert res.category_passed is True
        assert res.relevance_score == 5.0

@pytest.mark.asyncio
async def test_run_evaluation_suite(tmp_path, mock_prompt_config_v1):
    # Create temp dataset file
    dataset = [
        {"id": "case_1", "input": "I need help with billing", "expected_category": "billing", "expected_summary": "ex", "expected_difficulty": "easy"}
    ]
    dataset_file = os.path.join(tmp_path, "test_dataset.json")
    with open(dataset_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f)
        
    with patch("src.evaluator.IS_MOCK", True):
        run, results = await run_evaluation_suite(mock_prompt_config_v1, dataset_file, concurrency_limit=2)
        assert run.total_cases == 1
        assert run.pass_rate == 100.0
        assert len(results) == 1
        assert results[0].case_id == "case_1"
        assert run.total_cost > 0

def test_diff_results_logic():
    # Setup test results: base vs current
    base = [
        # case 1: passed category, relevance 4.5 -> passed
        TestResult(case_id="c1", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=4.5, latency=0.1, input_tokens=1, output_tokens=1),
        # case 2: failed category, relevance 4.0 -> failed
        TestResult(case_id="c2", input_text="in", expected_category="billing", expected_summary="ex", actual_category="technical", actual_summary="a", category_passed=False, relevance_score=4.0, latency=0.1, input_tokens=1, output_tokens=1),
        # case 3: passed category, relevance 3.0 -> failed (relevance too low)
        TestResult(case_id="c3", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=3.0, latency=0.1, input_tokens=1, output_tokens=1),
        # case 4: passed category, relevance 4.5 -> passed
        TestResult(case_id="c4", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=4.5, latency=0.1, input_tokens=1, output_tokens=1),
    ]

    current = [
        # case 1: passed category, relevance 3.0 -> failed (REGRESSION!)
        TestResult(case_id="c1", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=3.0, latency=0.1, input_tokens=1, output_tokens=1),
        # case 2: passed category, relevance 4.0 -> passed (IMPROVEMENT!)
        TestResult(case_id="c2", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=4.0, latency=0.1, input_tokens=1, output_tokens=1),
        # case 3: failed category, relevance 2.0 -> failed (STABLE FAIL)
        TestResult(case_id="c3", input_text="in", expected_category="billing", expected_summary="ex", actual_category="technical", actual_summary="a", category_passed=False, relevance_score=2.0, latency=0.1, input_tokens=1, output_tokens=1),
        # case 4: passed category, relevance 4.5 -> passed (STABLE PASS)
        TestResult(case_id="c4", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="a", category_passed=True, relevance_score=4.5, latency=0.1, input_tokens=1, output_tokens=1),
    ]

    diff = diff_results(current, base)
    
    assert len(diff["regressions"]) == 1
    assert diff["regressions"][0]["case_id"] == "c1"
    
    assert len(diff["improvements"]) == 1
    assert diff["improvements"][0]["case_id"] == "c2"

    assert len(diff["stable_pass"]) == 1
    assert diff["stable_pass"][0]["case_id"] == "c4"

    assert len(diff["stable_fail"]) == 1
    assert diff["stable_fail"][0]["case_id"] == "c3"

@pytest.mark.asyncio
@patch("src.evaluator.IS_MOCK", False)
async def test_evaluate_single_case_live_path(mock_prompt_config_v1):
    case = TestCase(id="c1", input="in", expected_category="billing", expected_summary="ex")
    semaphore = asyncio.Semaphore(1)
    
    # Successful classification run
    mock_run_data = {
        "category": "billing", "summary": "ex", "latency": 0.1, 
        "input_tokens": 10, "output_tokens": 5, "error": None
    }
    with patch("src.evaluator.classify_email", return_value=mock_run_data), \
         patch("src.evaluator.judge_summary_relevance", return_value=(4.5, "Good")):
        res = await evaluate_single_case(case, mock_prompt_config_v1, semaphore)
        assert res.category_passed is True
        assert res.relevance_score == 4.5
        assert res.error_message is None

    # Failed classification run (triggers elif run_data['error'] logic)
    mock_err_data = {
        "category": "general", "summary": "", "latency": 0.1, 
        "input_tokens": 0, "output_tokens": 0, "error": "API Failure"
    }
    with patch("src.evaluator.classify_email", return_value=mock_err_data):
        res = await evaluate_single_case(case, mock_prompt_config_v1, semaphore)
        assert res.category_passed is False
        assert res.relevance_score == 1.0
        assert "API Failure" in res.error_message

def test_diff_results_missing_case_id():
    # Test case when current result contains an ID not present in baseline mapping
    base = [TestResult(case_id="c1", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="ex", category_passed=True, relevance_score=5.0, latency=0.1, input_tokens=10, output_tokens=5)]
    current = [
        TestResult(case_id="c1", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="ex", category_passed=True, relevance_score=5.0, latency=0.1, input_tokens=10, output_tokens=5),
        TestResult(case_id="c2", input_text="in", expected_category="billing", expected_summary="ex", actual_category="billing", actual_summary="ex", category_passed=True, relevance_score=5.0, latency=0.1, input_tokens=10, output_tokens=5) # missing in base
    ]
    diff = diff_results(current, base)
    assert len(diff["stable_pass"]) == 1
    assert diff["stable_pass"][0]["case_id"] == "c1"

