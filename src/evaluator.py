import os
import json
import time
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import litellm

from src.config import PromptConfig, TestCase, TestResult, EvalRun
from src.classifier import classify_email, IS_MOCK

# Pricing details for gpt-4o-mini
INPUT_TOKEN_RATE = 0.15 / 1_000_000   # $0.15 per 1M tokens
OUTPUT_TOKEN_RATE = 0.60 / 1_000_000  # $0.60 per 1M tokens

# LLM-as-judge response schema
class JudgeOutput(BaseModel):
    score: float = Field(..., description="Relevance rating from 1.0 to 5.0")
    reason: str = Field(..., description="Explanation of why this rating was given")

# Mock relevance score helper to allow offline regression testing
def get_mock_relevance(case: TestCase, version: str) -> float:
    # Deterministic scoring based on case details and version
    diff = case.expected_difficulty
    
    if version == "1.0.0":
        if diff == "easy":
            return 5.0
        elif diff == "medium":
            return 4.5
        else:
            return 4.0
    else: # v2.0.0 prompt - degraded output summaries
        if diff == "easy":
            return 4.0
        elif diff == "medium":
            return 3.0
        else:
            return 2.0

async def judge_summary_relevance(
    email_text: str,
    expected_summary: str,
    actual_summary: str,
    client: Optional[Any] = None
) -> Tuple[float, str]:
    """
    Invokes an LLM-as-judge to rate the actual summary against the expected ground-truth summary.
    Returns a tuple of (score, reason).
    """
    if IS_MOCK:
        # Mock mode doesn't hit OpenAI
        return 0.0, "Mock mode active"
        
    prompt = f"""You are a customer support quality assurance auditor. Your job is to grade the quality of an AI-generated summary of a customer support email.

Compare the AI-generated actual summary with the human-written expected summary.

Customer Email:
---
{email_text}
---

Expected Ground-Truth Summary:
{expected_summary}

AI-Generated Actual Summary:
{actual_summary}

Grade the actual summary on a scale of 1.0 to 5.0:
- 5.0 (Excellent): Perfect representation of key issues, concise, conforms to summary norms.
- 4.0 (Good): Captures the core issues, but misses a minor detail or includes unnecessary words.
- 3.0 (Fair): Identifies the basic topic, but misses crucial context (e.g. key figures, direct request details) or contains pleasantries.
- 2.0 (Poor): Highly incomplete, contains pleasantries, or makes minor errors in details.
- 1.0 (Deficient): Factually incorrect, totally off-topic, or empty.

Ensure your score is a float or integer between 1.0 and 5.0.
"""

    try:
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise AI evaluator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format=JudgeOutput,
            max_tokens=200
        )
        content_str = response.choices[0].message.content or ""
        if content_str.startswith("```json"):
            content_str = content_str[7:]
        if content_str.endswith("```"):
            content_str = content_str[:-3]
        content_str = content_str.strip()
        
        parsed = JudgeOutput.model_validate_json(content_str)
        return parsed.score, parsed.reason
    except Exception as e:
        return 1.0, f"Error running LLM-as-judge: {str(e)}"

async def evaluate_single_case(
    case: TestCase,
    config: PromptConfig,
    semaphore: asyncio.Semaphore,
    client: Optional[Any] = None
) -> TestResult:
    """
    Evaluates a single test case.
    """
    async with semaphore:
        # 1. Run classifier
        run_data = await classify_email(case.input, config, client)
        
        # Determine exact match
        category_passed = run_data["category"].strip().lower() == case.expected_category.strip().lower()
        
        # 2. Score relevance
        if IS_MOCK:
            relevance_score = get_mock_relevance(case, config.version)
            judge_reason = "Mock evaluation"
        elif run_data["error"]:
            relevance_score = 1.0
            judge_reason = f"Error during classification: {run_data['error']}"
        else:
            relevance_score, judge_reason = await judge_summary_relevance(
                case.input, 
                case.expected_summary, 
                run_data["summary"],
                client
            )
            
        return TestResult(
            case_id=case.id,
            input_text=case.input,
            expected_category=case.expected_category,
            expected_summary=case.expected_summary,
            actual_category=run_data["category"],
            actual_summary=run_data["summary"],
            category_passed=category_passed,
            relevance_score=relevance_score,
            latency=run_data["latency"],
            input_tokens=run_data["input_tokens"],
            output_tokens=run_data["output_tokens"],
            error_message=run_data["error"] or (judge_reason if (judge_reason and judge_reason.startswith("Error")) else None)
        )

async def run_evaluation_suite(
    config: PromptConfig,
    dataset_path: str,
    concurrency_limit: int = 5
) -> Tuple[EvalRun, List[TestResult]]:
    """
    Runs the entire evaluation suite asynchronously.
    """
    # Load test cases
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases_json = json.load(f)
    cases = [TestCase(**c) for c in cases_json]
    
    client = None
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    # Run all test cases in parallel
    tasks = [evaluate_single_case(c, config, semaphore, client) for c in cases]
    results = await asyncio.gather(*tasks)
    
    # Calculate overall metrics
    total_cases = len(results)
    passed_categories = sum(1 for r in results if r.category_passed)
    pass_rate = (passed_categories / total_cases) * 100.0 if total_cases > 0 else 0.0
    avg_relevance = sum(r.relevance_score for r in results) / total_cases if total_cases > 0 else 0.0
    avg_latency = sum(r.latency for r in results) / total_cases if total_cases > 0 else 0.0
    
    total_input_tokens = sum(r.input_tokens for r in results)
    total_output_tokens = sum(r.output_tokens for r in results)
    total_tokens = total_input_tokens + total_output_tokens
    
    # Calculate costs
    total_cost = (total_input_tokens * INPUT_TOKEN_RATE) + (total_output_tokens * OUTPUT_TOKEN_RATE)
    
    # Create configuration hash to uniquely identify this prompt/setting setup
    config_str = f"{config.system_prompt}_{config.model}_{config.temperature}"
    config_hash = hashlib.md5(config_str.encode("utf-8")).hexdigest()
    
    run_id = f"run_{int(time.time())}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    run = EvalRun(
        id=run_id,
        timestamp=timestamp,
        prompt_version=config.version,
        model=config.model,
        total_cases=total_cases,
        pass_rate=pass_rate,
        avg_relevance=avg_relevance,
        avg_latency=avg_latency,
        total_tokens=total_tokens,
        total_cost=total_cost,
        config_hash=config_hash,
        is_baseline=False
    )
    
    return run, results

def diff_results(current_results: List[TestResult], baseline_results: List[TestResult]) -> Dict[str, Any]:
    """
    Compares the results of the current run against baseline results.
    Identifies regressions and improvements.
    """
    baseline_map = {r.case_id: r for r in baseline_results}
    
    regressions = []
    improvements = []
    stable_pass = []
    stable_fail = []
    
    for current in current_results:
        baseline = baseline_map.get(current.case_id)
        if not baseline:
            continue
            
        # Define pass criteria: category matches AND summary relevance >= 3.5
        baseline_passed = baseline.category_passed and baseline.relevance_score >= 3.5
        current_passed = current.category_passed and current.relevance_score >= 3.5
        
        diff_info = {
            "case_id": current.case_id,
            "input_text": current.input_text,
            "baseline": {
                "category": baseline.actual_category,
                "summary": baseline.actual_summary,
                "category_passed": baseline.category_passed,
                "relevance_score": baseline.relevance_score,
                "latency": baseline.latency
            },
            "current": {
                "category": current.actual_category,
                "summary": current.actual_summary,
                "category_passed": current.category_passed,
                "relevance_score": current.relevance_score,
                "latency": current.latency
            }
        }
        
        if baseline_passed and not current_passed:
            regressions.append(diff_info)
        elif not baseline_passed and current_passed:
            improvements.append(diff_info)
        elif current_passed:
            stable_pass.append(diff_info)
        else:
            stable_fail.append(diff_info)
            
    return {
        "regressions": regressions,
        "improvements": improvements,
        "stable_pass": stable_pass,
        "stable_fail": stable_fail
    }
