import pytest
import os
from unittest.mock import patch

from src.config import EvalRun, TestResult
from src.reporter import generate_report

def test_generate_report(tmp_path):
    run = EvalRun(
        id="run_rep_test",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0.0",
        model="gpt-4o-mini",
        total_cases=1,
        pass_rate=100.0,
        avg_relevance=5.0,
        avg_latency=0.2,
        total_tokens=15,
        total_cost=0.0001,
        config_hash="abc",
        is_baseline=True
    )
    
    results = [
        TestResult(
            case_id="case_1",
            input_text="in",
            expected_category="billing",
            expected_summary="ex",
            actual_category="billing",
            actual_summary="ex",
            category_passed=True,
            relevance_score=5.0,
            latency=0.2,
            input_tokens=10,
            output_tokens=5
        )
    ]
    
    diff = {"regressions": [], "improvements": [], "stable_pass": [{"case_id": "case_1"}], "stable_fail": []}
    drift = {"drift_detected": False, "message": "Performance stable."}
    
    # Mock database history query so we have dummy runs for Chart.js
    mock_history = [run]
    
    # Patch reports directory path to point inside tmp_path
    reports_dir = os.path.join(tmp_path, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    with patch("src.reporter.get_run_history", return_value=mock_history):
        with patch("src.reporter.os.path.dirname") as mock_dir:
            # Mock dirname so the report compiles to our temporary reports directory
            mock_dir.return_value = tmp_path
            
            report_file = generate_report(
                run=run,
                results=results,
                diff=diff,
                status="PASSED",
                drift=drift,
                baseline=run
            )
            
            assert os.path.exists(report_file)
            assert f"report_{run.id}.html" in report_file
            
            latest_file = os.path.join(reports_dir, "latest.html")
            assert os.path.exists(latest_file)
            
            # Read html and check content
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "run_rep_test" in content
            assert "gpt-4o-mini" in content
            assert "Diagnostics" in content
