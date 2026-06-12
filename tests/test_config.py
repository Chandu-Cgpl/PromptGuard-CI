import pytest
from pydantic import ValidationError
from src.config import PromptConfig, ClassifierOutput, TestCase, TestResult, EvalRun

def test_prompt_config_serialization():
    data = {
        "version": "1.0.0",
        "timestamp": "2026-06-12T10:00:00Z",
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "system_prompt": "Test Prompt",
        "few_shot_examples": [{"input": "hi", "expected_output": {"category": "general", "summary": "hi"}}]
    }
    config = PromptConfig(**data)
    assert config.version == "1.0.0"
    assert len(config.few_shot_examples) == 1
    assert config.few_shot_examples[0]["input"] == "hi"

def test_classifier_output_serialization():
    output = ClassifierOutput(category="billing", summary="billing issue description")
    assert output.category == "billing"
    assert output.summary == "billing issue description"
    
    # Missing required fields should raise ValidationError
    with pytest.raises(ValidationError):
        ClassifierOutput(category="billing") # type: ignore

def test_test_case_defaults():
    case = TestCase(id="c1", input="hello", expected_category="general", expected_summary="greeting")
    assert case.expected_difficulty == "easy"
    assert case.notes is None

def test_test_result_and_eval_run():
    result = TestResult(
        case_id="case_1",
        input_text="in",
        expected_category="billing",
        expected_summary="ex",
        actual_category="billing",
        actual_summary="act",
        category_passed=True,
        relevance_score=5.0,
        latency=0.1,
        input_tokens=10,
        output_tokens=5
    )
    assert result.category_passed is True

    run = EvalRun(
        id="run_1",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0",
        model="gpt-4o",
        total_cases=1,
        pass_rate=100.0,
        avg_relevance=5.0,
        avg_latency=0.1,
        total_tokens=15,
        total_cost=0.0001,
        config_hash="abc",
        is_baseline=True
    )
    assert run.is_baseline is True
