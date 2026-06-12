import sqlite3
import os
import json
from typing import List, Dict, Any, Optional
from src.config import EvalRun, TestResult

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_history.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create eval_runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eval_runs (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        model TEXT NOT NULL,
        total_cases INTEGER NOT NULL,
        pass_rate REAL NOT NULL,
        avg_relevance REAL NOT NULL,
        avg_latency REAL NOT NULL,
        total_tokens INTEGER NOT NULL,
        total_cost REAL NOT NULL,
        config_hash TEXT NOT NULL,
        is_baseline INTEGER DEFAULT 0
    )
    """)
    
    # Create test_results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_results (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        case_id TEXT NOT NULL,
        input_text TEXT NOT NULL,
        expected_category TEXT NOT NULL,
        expected_summary TEXT NOT NULL,
        actual_category TEXT NOT NULL,
        actual_summary TEXT NOT NULL,
        category_passed INTEGER NOT NULL,
        relevance_score REAL NOT NULL,
        latency REAL NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        error_message TEXT,
        FOREIGN KEY (run_id) REFERENCES eval_runs (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

def save_run(run: EvalRun, results: List[TestResult]):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # If this run is marked as baseline, unset baseline on all other runs first
        if run.is_baseline:
            cursor.execute("UPDATE eval_runs SET is_baseline = 0")
            
        cursor.execute("""
        INSERT INTO eval_runs (
            id, timestamp, prompt_version, model, total_cases, 
            pass_rate, avg_relevance, avg_latency, total_tokens, total_cost, 
            config_hash, is_baseline
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.id, run.timestamp, run.prompt_version, run.model, run.total_cases,
            run.pass_rate, run.avg_relevance, run.avg_latency, run.total_tokens, run.total_cost,
            run.config_hash, 1 if run.is_baseline else 0
        ))
        
        for r in results:
            result_id = f"{run.id}_{r.case_id}"
            cursor.execute("""
            INSERT INTO test_results (
                id, run_id, case_id, input_text, expected_category, expected_summary,
                actual_category, actual_summary, category_passed, relevance_score,
                latency, input_tokens, output_tokens, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, run.id, r.case_id, r.input_text, r.expected_category, r.expected_summary,
                r.actual_category, r.actual_summary, 1 if r.category_passed else 0, r.relevance_score,
                r.latency, r.input_tokens, r.output_tokens, r.error_message
            ))
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_baseline_run() -> Optional[EvalRun]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM eval_runs WHERE is_baseline = 1 ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return EvalRun(
            id=row["id"],
            timestamp=row["timestamp"],
            prompt_version=row["prompt_version"],
            model=row["model"],
            total_cases=row["total_cases"],
            pass_rate=row["pass_rate"],
            avg_relevance=row["avg_relevance"],
            avg_latency=row["avg_latency"],
            total_tokens=row["total_tokens"],
            total_cost=row["total_cost"],
            config_hash=row["config_hash"],
            is_baseline=bool(row["is_baseline"])
        )
    return None

def get_latest_run() -> Optional[EvalRun]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM eval_runs ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return EvalRun(
            id=row["id"],
            timestamp=row["timestamp"],
            prompt_version=row["prompt_version"],
            model=row["model"],
            total_cases=row["total_cases"],
            pass_rate=row["pass_rate"],
            avg_relevance=row["avg_relevance"],
            avg_latency=row["avg_latency"],
            total_tokens=row["total_tokens"],
            total_cost=row["total_cost"],
            config_hash=row["config_hash"],
            is_baseline=bool(row["is_baseline"])
        )
    return None

def set_baseline_run(run_id: str):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE eval_runs SET is_baseline = 0")
        cursor.execute("UPDATE eval_runs SET is_baseline = 1 WHERE id = ?", (run_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_results_for_run(run_id: str) -> List[TestResult]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM test_results WHERE run_id = ?", (run_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append(TestResult(
            case_id=r["case_id"],
            input_text=r["input_text"],
            expected_category=r["expected_category"],
            expected_summary=r["expected_summary"],
            actual_category=r["actual_category"],
            actual_summary=r["actual_summary"],
            category_passed=bool(r["category_passed"]),
            relevance_score=r["relevance_score"],
            latency=r["latency"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            error_message=r["error_message"]
        ))
    return results

def get_run_history(limit: int = 20) -> List[EvalRun]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM eval_runs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    runs = []
    for row in rows:
        runs.append(EvalRun(
            id=row["id"],
            timestamp=row["timestamp"],
            prompt_version=row["prompt_version"],
            model=row["model"],
            total_cases=row["total_cases"],
            pass_rate=row["pass_rate"],
            avg_relevance=row["avg_relevance"],
            avg_latency=row["avg_latency"],
            total_tokens=row["total_tokens"],
            total_cost=row["total_cost"],
            config_hash=row["config_hash"],
            is_baseline=bool(row["is_baseline"])
        ))
    return runs
