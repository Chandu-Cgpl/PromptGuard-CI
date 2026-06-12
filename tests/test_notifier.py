import pytest
import os
import json
from unittest.mock import patch, MagicMock
from src.notifier import send_slack_alert
from src.config import EvalRun

@pytest.fixture
def sample_run() -> EvalRun:
    return EvalRun(
        id="run_test_alert",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0.0",
        model="gpt-4o-mini",
        total_cases=10,
        pass_rate=90.0,
        avg_relevance=4.5,
        avg_latency=0.3,
        total_tokens=100,
        total_cost=0.00015,
        config_hash="abc",
        is_baseline=False
    )

def test_slack_alert_mock_fallback(sample_run):
    # Set workspace root relatively
    with patch("src.notifier.SLACK_WEBHOOK_URL", ""):
        # Patch builtins.open to mock writing the payload to reports
        with patch("builtins.open", MagicMock()) as mock_file:
            res = send_slack_alert(
                run=sample_run,
                status="WARNING",
                diff={"regressions": [{"case_id": "c1"}], "improvements": []},
                report_path="reports/latest.html"
            )
            
            assert res["sent"] is False
            assert "saved_to" in res
            mock_file.assert_called_once()

@patch("urllib.request.urlopen")
def test_slack_alert_live_success(mock_urlopen, sample_run):
    # Mock urlopen context manager return object and read value
    mock_context = MagicMock()
    mock_context.read.return_value = b"ok"
    mock_urlopen.return_value.__enter__.return_value = mock_context
    
    with patch("src.notifier.SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/test"):
        res = send_slack_alert(
            run=sample_run,
            status="PASSED",
            diff={"regressions": [], "improvements": []},
            report_path="reports/latest.html"
        )
        
        assert res["sent"] is True
        assert res["response"] == "ok"
        mock_urlopen.assert_called_once()

@patch("urllib.request.urlopen")
def test_slack_alert_live_failure(mock_urlopen, sample_run):
    mock_urlopen.side_effect = Exception("HTTP Error 500")
    
    with patch("src.notifier.SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/test"):
        res = send_slack_alert(
            run=sample_run,
            status="CRITICAL",
            diff={"regressions": [{"case_id": "c1"}], "improvements": []},
            report_path="reports/latest.html"
        )
        
        assert res["sent"] is False
        assert "HTTP Error 500" in res["error"]

def test_slack_alert_advanced_features(sample_run):
    # Test case 1: positive deltas, drift, and > 10 regressions
    baseline_run = EvalRun(
        id="run_baseline",
        timestamp="2026-06-12T09:00:00Z",
        prompt_version="0.9.0",
        model="gpt-4o-mini",
        total_cases=10,
        pass_rate=80.0,
        avg_relevance=4.0,
        avg_latency=0.3,
        total_tokens=100,
        total_cost=0.00015,
        config_hash="abc",
        is_baseline=True
    )
    drift_info = {
        "drift_detected": True,
        "message": "Model performance is drifting."
    }
    regressions = [{"case_id": f"c{i}"} for i in range(11)]
    
    with patch("src.notifier.SLACK_WEBHOOK_URL", ""):
        with patch("builtins.open", MagicMock()):
            res = send_slack_alert(
                run=sample_run,
                status="WARNING",
                diff={"regressions": regressions, "improvements": []},
                report_path="reports/latest.html",
                baseline=baseline_run,
                drift_info=drift_info
            )
            assert res["sent"] is False
            
    # Test case 2: negative/zero deltas
    baseline_run_better = EvalRun(
        id="run_baseline_better",
        timestamp="2026-06-12T09:00:00Z",
        prompt_version="0.9.0",
        model="gpt-4o-mini",
        total_cases=10,
        pass_rate=100.0,
        avg_relevance=5.0,
        avg_latency=0.3,
        total_tokens=100,
        total_cost=0.00015,
        config_hash="abc",
        is_baseline=True
    )
    with patch("src.notifier.SLACK_WEBHOOK_URL", ""):
        with patch("builtins.open", MagicMock()):
            res = send_slack_alert(
                run=sample_run,
                status="WARNING",
                diff={"regressions": [], "improvements": []},
                report_path="reports/latest.html",
                baseline=baseline_run_better
            )
            assert res["sent"] is False
