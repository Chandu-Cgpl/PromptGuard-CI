from typing import Dict, Any, Optional
from src.database import get_run_history, get_baseline_run

def check_performance_drift(
    rolling_window: int = 7, 
    drift_threshold_pct: float = 4.0
) -> Dict[str, Any]:
    """
    Computes a rolling average of recent runs and checks for downward drift
    compared to the active baseline.
    """
    baseline = get_baseline_run()
    if not baseline:
        return {
            "drift_detected": False,
            "message": "No baseline established yet. Skipping drift detection.",
            "rolling_avg_pass_rate": 0.0,
            "rolling_avg_relevance": 0.0,
            "pass_rate_drift": 0.0,
            "relevance_drift": 0.0
        }
        
    recent_runs = get_run_history(limit=rolling_window)
    
    # We need at least a few runs to check for drift
    if len(recent_runs) < 3:
        return {
            "drift_detected": False,
            "message": f"Insufficient run history ({len(recent_runs)}/3 runs). Skipping drift detection.",
            "rolling_avg_pass_rate": 0.0,
            "rolling_avg_relevance": 0.0,
            "pass_rate_drift": 0.0,
            "relevance_drift": 0.0
        }
        
    # Compute rolling averages
    total_runs = len(recent_runs)
    sum_pass_rate = sum(run.pass_rate for run in recent_runs)
    sum_relevance = sum(run.avg_relevance for run in recent_runs)
    
    rolling_avg_pass_rate = sum_pass_rate / total_runs
    rolling_avg_relevance = sum_relevance / total_runs
    
    # Compare with baseline
    pass_rate_drift = rolling_avg_pass_rate - baseline.pass_rate
    relevance_drift = rolling_avg_relevance - baseline.avg_relevance
    
    # Drift is detected if the rolling average drops significantly below the baseline
    # (e.g. baseline is 94%, rolling avg is 89%, drift is -5.0%, threshold is 4.0% drop i.e. drift <= -4.0)
    drift_detected = pass_rate_drift <= -drift_threshold_pct
    
    if drift_detected:
        message = (
            f"Slow drift warning! Rolling average accuracy ({rolling_avg_pass_rate:.1f}%) "
            f"has dropped by {-pass_rate_drift:.1f}% below the baseline ({baseline.pass_rate:.1f}%) "
            f"over the last {total_runs} runs."
        )
    else:
        message = (
            f"Performance stable. Rolling accuracy is {rolling_avg_pass_rate:.1f}% "
            f"(diff from baseline: {pass_rate_drift:+.1f}%)."
        )
        
    return {
        "drift_detected": drift_detected,
        "message": message,
        "rolling_avg_pass_rate": rolling_avg_pass_rate,
        "rolling_avg_relevance": rolling_avg_relevance,
        "pass_rate_drift": pass_rate_drift,
        "relevance_drift": relevance_drift,
        "window_size": total_runs
    }
