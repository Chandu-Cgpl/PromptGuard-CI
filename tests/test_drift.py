import pytest
import sqlite3
import time
from src.config import EvalRun, TestResult
from src.database import init_db, save_run, set_baseline_run
from src.drift import check_performance_drift

def seed_run(run_id: str, prompt_ver: str, accuracy: float, relevance: float, is_base: bool = False):
    run = EvalRun(
        id=run_id,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        prompt_version=prompt_ver,
        model="gpt-4o-mini",
        total_cases=10,
        pass_rate=accuracy,
        avg_relevance=relevance,
        avg_latency=0.3,
        total_tokens=100,
        total_cost=0.00015,
        config_hash="hash_h",
        is_baseline=is_base
    )
    save_run(run, [])
    if is_base:
        set_baseline_run(run_id)

def test_drift_no_baseline():
    init_db()
    # No runs seeded yet
    res = check_performance_drift()
    assert res["drift_detected"] is False
    assert "No baseline" in res["message"]

def test_drift_insufficient_history():
    init_db()
    
    # Seed only 1 baseline run and 1 regular run (total 2 runs, < 3 requirement)
    seed_run("run_1", "1.0.0", 95.0, 4.8, is_base=True)
    seed_run("run_2", "1.0.0", 93.0, 4.7)
    
    res = check_performance_drift()
    assert res["drift_detected"] is False
    assert "Insufficient run history" in res["message"]

def test_drift_stable_performance():
    init_db()
    
    # Seed 1 baseline (95% accuracy) and 3 subsequent stable runs
    seed_run("run_1", "1.0.0", 95.0, 4.8, is_base=True)
    seed_run("run_2", "1.0.0", 94.0, 4.7)
    seed_run("run_3", "1.0.0", 93.0, 4.7)
    seed_run("run_4", "1.0.0", 95.0, 4.8)
    
    res = check_performance_drift(rolling_window=7, drift_threshold_pct=4.0)
    assert res["drift_detected"] is False
    assert "Performance stable" in res["message"]
    # Rolling average: (95+94+93+95)/4 = 94.25%. Delta = 94.25 - 95.0 = -0.75%
    assert abs(res["pass_rate_drift"] - (-0.75)) < 0.01

def test_drift_detected_warning():
    init_db()
    
    # Seed 1 baseline (95% accuracy) and 3 degraded runs (average 90% accuracy)
    # Average accuracy drop is 5% which is > 4.0% threshold
    seed_run("run_1", "1.0.0", 95.0, 4.8, is_base=True)
    seed_run("run_2", "1.0.0", 90.0, 3.5)
    seed_run("run_3", "1.0.0", 89.0, 3.2)
    seed_run("run_4", "1.0.0", 90.0, 3.6)
    
    res = check_performance_drift(rolling_window=7, drift_threshold_pct=4.0)
    assert res["drift_detected"] is True
    assert "Slow drift warning" in res["message"]
    # Rolling average: (95+90+89+90)/4 = 91.0%. Delta = 91.0 - 95.0 = -4.0%
    assert abs(res["pass_rate_drift"] - (-4.0)) < 0.01
