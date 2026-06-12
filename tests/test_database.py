import pytest
import sqlite3
import os
from unittest.mock import patch, MagicMock
from src.config import EvalRun, TestResult
from src.database import (
    init_db,
    save_run,
    get_baseline_run,
    get_latest_run,
    set_baseline_run,
    get_results_for_run,
    get_run_history,
    get_db_connection
)

def test_database_lifecycle():
    # 1. Initialize DB
    init_db()
    
    # Check that tables exist
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()
    
    assert "eval_runs" in tables
    assert "test_results" in tables

def test_save_and_retrieve_runs():
    init_db()
    
    run_1 = EvalRun(
        id="run_001",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0.0",
        model="gpt-4o-mini",
        total_cases=2,
        pass_rate=50.0,
        avg_relevance=4.0,
        avg_latency=0.5,
        total_tokens=100,
        total_cost=0.00015,
        config_hash="hash_v1",
        is_baseline=True
    )
    
    results = [
        TestResult(
            case_id="case_1",
            input_text="charge",
            expected_category="billing",
            expected_summary="ex",
            actual_category="billing",
            actual_summary="ex",
            category_passed=True,
            relevance_score=5.0,
            latency=0.3,
            input_tokens=50,
            output_tokens=10
        ),
        TestResult(
            case_id="case_2",
            input_text="login crash",
            expected_category="technical",
            expected_summary="ex",
            actual_category="general", # failed prediction
            actual_summary="ex",
            category_passed=False,
            relevance_score=3.0,
            latency=0.7,
            input_tokens=30,
            output_tokens=10
        )
    ]
    
    # Save first run
    save_run(run_1, results)
    
    # Verify latest run and baseline run matches
    latest = get_latest_run()
    assert latest is not None
    assert latest.id == "run_001"
    assert latest.is_baseline is True

    baseline = get_baseline_run()
    assert baseline is not None
    assert baseline.id == "run_001"
    
    # Retrieve results
    db_results = get_results_for_run("run_001")
    assert len(db_results) == 2
    assert db_results[0].case_id == "case_1"
    assert db_results[0].category_passed is True
    assert db_results[1].case_id == "case_2"
    assert db_results[1].category_passed is False

    # Check history
    history = get_run_history(limit=5)
    assert len(history) == 1
    assert history[0].id == "run_001"

def test_baseline_promotion_flow():
    init_db()
    
    run_1 = EvalRun(
        id="run_001",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0.0",
        model="gpt-4o-mini",
        total_cases=1,
        pass_rate=100.0,
        avg_relevance=5.0,
        avg_latency=0.1,
        total_tokens=10,
        total_cost=0.0,
        config_hash="h1",
        is_baseline=True
    )
    save_run(run_1, [])
    
    # Save a second run NOT marked as baseline during save
    run_2 = EvalRun(
        id="run_002",
        timestamp="2026-06-12T10:15:00Z",
        prompt_version="2.0.0",
        model="gpt-4o-mini",
        total_cases=1,
        pass_rate=80.0,
        avg_relevance=4.0,
        avg_latency=0.2,
        total_tokens=20,
        total_cost=0.0,
        config_hash="h2",
        is_baseline=False
    )
    save_run(run_2, [])
    
    # Active baseline should still be run_001
    assert get_baseline_run().id == "run_001"
    
    # Promote run_002 to baseline
    set_baseline_run("run_002")
    
    # Active baseline should now be run_002
    assert get_baseline_run().id == "run_002"
    
    # And run_001's is_baseline flag should have been unset
    conn = get_db_connection()
    row = conn.execute("SELECT is_baseline FROM eval_runs WHERE id='run_001'").fetchone()
    conn.close()
    assert row["is_baseline"] == 0

def test_database_save_error_rollback():
    init_db()
    run = EvalRun(
        id="run_err",
        timestamp="2026-06-12T10:00:00Z",
        prompt_version="1.0.0",
        model="gpt-4o-mini",
        total_cases=1,
        pass_rate=100.0,
        avg_relevance=5.0,
        avg_latency=0.1,
        total_tokens=10,
        total_cost=0.0,
        config_hash="h1",
        is_baseline=False
    )
    
    # Passing results with incomplete/invalid fields to trigger constraint/type mismatch inside transaction loops
    # For instance, missing case_id raises exception or we trigger SQLite syntax error.
    # To trigger error deterministically, let's pass an object that cannot be read as a result, like None.
    with pytest.raises(Exception):
        save_run(run, [None]) # type: ignore
        
    # Verify that run was rolled back and not committed
    conn = get_db_connection()
    row = conn.execute("SELECT count(*) as cnt FROM eval_runs WHERE id='run_err'").fetchone()
    conn.close()
    assert row["cnt"] == 0

def test_get_latest_run_empty():
    init_db()
    # Delete all runs to test empty table case
    conn = get_db_connection()
    conn.execute("DELETE FROM eval_runs")
    conn.commit()
    conn.close()
    
    assert get_latest_run() is None
    assert get_baseline_run() is None

def test_set_baseline_run_error():
    init_db()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = [None, None, sqlite3.Error("Mock DB Error")]
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("src.database.get_db_connection", return_value=mock_conn):
        with pytest.raises(sqlite3.Error):
            set_baseline_run("run_mock")

