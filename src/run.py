import os
import sys
import yaml
import asyncio
import argparse
from typing import Dict, Any

from src.config import PromptConfig
from src.database import save_run, get_baseline_run, get_results_for_run, set_baseline_run
from src.evaluator import run_evaluation_suite, diff_results
from src.drift import check_performance_drift
from src.reporter import generate_report
from src.notifier import send_slack_alert
from src.classifier import IS_MOCK

async def main_async():
    parser = argparse.ArgumentParser(description="Model Regression Evaluation Pipeline")
    parser.add_argument("--prompt", required=True, help="Path to prompt YAML configuration file")
    parser.add_argument("--baseline", action="store_true", help="Set this run as the new baseline")
    parser.add_argument("--dataset", default=os.path.join("data", "golden_dataset.json"), help="Path to golden dataset JSON")
    parser.add_argument("--warning-threshold", type=float, default=3.0, help="Accuracy drop percentage to trigger warning alert (e.g. 3.0)")
    parser.add_argument("--critical-threshold", type=float, default=8.0, help="Accuracy drop percentage to fail build and trigger critical alert (e.g. 8.0)")
    parser.add_argument("--drift-threshold", type=float, default=4.0, help="Rolling performance drift threshold percentage (e.g. 4.0)")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent LLM API requests")
    
    args = parser.parse_args()

    print("=" * 60)
    print("[START] STARTING MODEL REGRESSION EVALUATION")
    print(f"[CONFIG] Config: {args.prompt}")
    print(f"[DATA] Dataset: {args.dataset}")
    print(f"[MODE] Mode: {'MOCK (Offline)' if IS_MOCK else 'LIVE (OpenAI API)'}")
    print("=" * 60)

    # 1. Load Prompt Config
    if not os.path.exists(args.prompt):
        print(f"[ERROR] Prompt file '{args.prompt}' not found.")
        sys.exit(2)
        
    with open(args.prompt, "r", encoding="utf-8") as f:
        prompt_raw = yaml.safe_load(f)
    config = PromptConfig(**prompt_raw)

    # 2. Fetch Active Baseline before running this eval (to do diffs)
    baseline_run = get_baseline_run()
    baseline_results = []
    if baseline_run:
        print(f"[BASELINE] Found Active Baseline: Run ID `{baseline_run.id}` (Prompt v{baseline_run.prompt_version}, Accuracy: {baseline_run.pass_rate:.1f}%)")
        baseline_results = get_results_for_run(baseline_run.id)
    else:
        print("[INFO] No active baseline established in database. This run will be used as standard baseline if --baseline is set.")

    # 3. Run Evaluation Suite
    print(f"\n[RUN] Evaluating {config.model} on golden dataset...")
    run, results = await run_evaluation_suite(config, args.dataset, args.concurrency)
    print(f"[SUCCESS] Evaluation complete. Total cases: {run.total_cases}. Accuracy: {run.pass_rate:.1f}%. Avg Relevance: {run.avg_relevance:.2f}/5")

    # 4. Perform comparison analysis if baseline exists
    diff = {"regressions": [], "improvements": [], "stable_pass": [], "stable_fail": []}
    status = "PASSED"
    accuracy_delta = 0.0
    
    if baseline_run and baseline_results:
        diff = diff_results(results, baseline_results)
        accuracy_delta = run.pass_rate - baseline_run.pass_rate
        
        # Calculate status based on thresholds
        if accuracy_delta <= -args.critical_threshold:
            status = "CRITICAL"
        elif accuracy_delta <= -args.warning_threshold:
            status = "WARNING"
            
        print(f"\n[DIFF] Comparison against Baseline Run `{baseline_run.id}`:")
        print(f"   Delta Accuracy: {accuracy_delta:+.1f}%")
        print(f"   Regressions: {len(diff['regressions'])} case(s)")
        print(f"   Improvements: {len(diff['improvements'])} case(s)")
    else:
        # If this is the very first run and no baseline exists, make it a baseline anyway or treat it as baseline
        if not baseline_run:
            args.baseline = True

    # 5. Check performance drift
    if args.baseline:
        run.is_baseline = True
        
    # We save first so drift detection incorporates current run history
    save_run(run, results)
    if args.baseline:
        set_baseline_run(run.id)
        # Re-fetch baseline to sync current run context
        baseline_run = run
        print(f"[BASELINE] Run `{run.id}` marked as the new Active Baseline.")

    drift_info = check_performance_drift(rolling_window=7, drift_threshold_pct=args.drift_threshold)
    print(f"\n[DRIFT] Performance Drift Check:")
    print(f"   Status: {'DRIFT DETECTED' if drift_info['drift_detected'] else 'Stable'}")
    print(f"   Message: {drift_info['message']}")

    # 6. Generate HTML Report
    report_path = generate_report(run, results, diff, status, drift_info, baseline_run)
    print(f"\n[REPORT] HTML diagnostics report written to:\n   {report_path}")

    # 7. Alert Slack
    alert_res = send_slack_alert(run, status, diff, report_path, drift_info, baseline_run)
    if alert_res.get("sent"):
        print("[ALERT] Slack webhook alert sent successfully!")
    elif alert_res.get("saved_to"):
        print(f"[ALERT] Slack notification logged locally (Mock mode) to:\n   {alert_res['saved_to']}")
    elif alert_res.get("error"):
        print(f"[WARNING] Slack notification failed: {alert_res['error']}")

    print("\n" + "=" * 60)
    print(f"[SUMMARY] SUMMARY OF RUN `{run.id}`")
    print(f"   Result Status: {status}")
    print(f"   Category Accuracy: {run.pass_rate:.1f}% ({'+' if accuracy_delta > 0 else ''}{accuracy_delta:.1f}% delta)")
    print(f"   Total Cases Flipped Pass->Fail (Regressions): {len(diff['regressions'])}")
    print(f"   Rolling 7-run Drift Warning: {'ACTIVE' if drift_info['drift_detected'] else 'CLEAR'}")
    print("=" * 60)

    # 8. Set exit code: break build on critical regressions
    if status == "CRITICAL":
        print("[FAIL] Build Failed: Critical regression threshold exceeded. Exiting with code 1.")
        sys.exit(1)
    else:
        print("[SUCCESS] Build Succeeded. Exiting with code 0.")
        sys.exit(0)

def main():
    # Helper to execute async main in standard Python entry point
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
