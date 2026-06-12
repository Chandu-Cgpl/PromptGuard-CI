import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
import runpy

from src.run import main_async

# Standard config return mock
MOCK_PROMPT_YAML = {
    "version": "1.0.0",
    "timestamp": "2026-06-12T10:00:00Z",
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "system_prompt": "Classifier instructions",
    "few_shot_examples": []
}

@pytest.mark.asyncio
async def test_run_missing_prompt_file():
    with patch("os.path.exists", return_value=False):
        with patch("sys.argv", ["run.py", "--prompt", "invalid_prompt.yaml"]):
            with pytest.raises(SystemExit) as sysexit:
                await main_async()
            assert sysexit.value.code == 2

@pytest.mark.asyncio
async def test_run_main_success_establish_baseline():
    # Mocks file open and exists checks
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", MagicMock()):
            with patch("yaml.safe_load", return_value=MOCK_PROMPT_YAML):
                # Mock evaluators
                mock_run = MagicMock(id="run_base", pass_rate=90.0, avg_relevance=4.5, total_cases=5, is_baseline=False)
                mock_results = []
                
                with patch("src.run.run_evaluation_suite", return_value=(mock_run, mock_results)) as mock_suite, \
                     patch("src.run.get_baseline_run", return_value=None), \
                     patch("src.run.save_run") as mock_save, \
                     patch("src.run.set_baseline_run") as mock_set_baseline, \
                     patch("src.run.generate_report", return_value="/reports/report_run_base.html") as mock_report, \
                     patch("src.run.send_slack_alert", return_value={"sent": True}) as mock_slack:
                         
                    with patch("sys.argv", ["run.py", "--prompt", "prompts/v1.yaml", "--baseline"]):
                        with pytest.raises(SystemExit) as sysexit:
                            await main_async()
                            
                        assert sysexit.value.code == 0
                        mock_suite.assert_called_once()
                        mock_save.assert_called_once()
                        mock_set_baseline.assert_called_once()
                        mock_report.assert_called_once()
                        mock_slack.assert_called_once()

@pytest.mark.asyncio
async def test_run_main_warning_and_critical_regression():
    # 1. Test Warning regression status
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()), \
         patch("yaml.safe_load", return_value=MOCK_PROMPT_YAML):
             
        # Mock active baseline run (95.0% accuracy)
        mock_baseline = MagicMock(id="run_base", pass_rate=95.0, avg_relevance=4.8)
        # Mock current run (91.0% accuracy, -4.0% drop)
        mock_current = MagicMock(id="run_curr", pass_rate=91.0, avg_relevance=4.0, total_cases=5, is_baseline=False)
        
        with patch("src.run.run_evaluation_suite", return_value=(mock_current, [])) as mock_suite, \
             patch("src.run.get_baseline_run", return_value=mock_baseline), \
             patch("src.run.get_results_for_run", return_value=[MagicMock(case_id="case_1")]), \
             patch("src.run.save_run") as mock_save, \
             patch("src.run.generate_report", return_value="/reports/report.html"), \
             patch("src.run.send_slack_alert", return_value={"saved_to": "path/log.json"}):
                 
            # Warning case: drop is -4%, warning threshold is 3%, critical is 8% -> WARNING status, exit code 0
            with patch("sys.argv", ["run.py", "--prompt", "prompts/v2.yaml", "--warning-threshold", "3.0", "--critical-threshold", "8.0"]):
                with pytest.raises(SystemExit) as sysexit:
                    await main_async()
                assert sysexit.value.code == 0

            # Critical case: drop is -4%, warning is 1%, critical is 3% -> CRITICAL status, exit code 1
            with patch("sys.argv", ["run.py", "--prompt", "prompts/v2.yaml", "--warning-threshold", "1.0", "--critical-threshold", "3.0"]):
                with pytest.raises(SystemExit) as sysexit:
                    await main_async()
                assert sysexit.value.code == 1

def test_run_script_execution():
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()), \
         patch("yaml.safe_load", return_value=MOCK_PROMPT_YAML), \
         patch("src.evaluator.run_evaluation_suite", return_value=(MagicMock(id="run_base", pass_rate=90.0, avg_relevance=4.5, total_cases=5, is_baseline=False), [])), \
         patch("src.database.get_baseline_run", return_value=None), \
         patch("src.database.save_run"), \
         patch("src.reporter.generate_report", return_value="/reports/report_run_base.html"), \
         patch("src.notifier.send_slack_alert", return_value={"error": "Failed to connect"}):
             
        with patch("sys.argv", ["run.py", "--prompt", "prompts/v1.yaml"]):
            with pytest.raises(SystemExit) as sysexit:
                runpy.run_path("src/run.py", run_name="__main__")
            assert sysexit.value.code == 0
