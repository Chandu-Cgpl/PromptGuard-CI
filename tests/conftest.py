import pytest
import os
import shutil
from typing import Generator
import src.database
from src.config import PromptConfig

@pytest.fixture(autouse=True)
def test_db_isolation(tmp_path) -> Generator[None, None, None]:
    """
    Autouse fixture that patches the SQLite database path to a temporary file
    for every test execution. Ensures zero side-effects on production databases.
    """
    # Create temp database file
    temp_db_file = os.path.join(tmp_path, "test_eval_history.db")
    original_db_path = src.database.DB_PATH
    
    # Patch database path
    src.database.DB_PATH = temp_db_file
    
    yield
    
    # Revert database path
    src.database.DB_PATH = original_db_path

@pytest.fixture
def mock_prompt_config_v1() -> PromptConfig:
    return PromptConfig(
        version="1.0.0",
        timestamp="2026-06-12T10:00:00Z",
        model="gpt-4o-mini",
        temperature=0.0,
        system_prompt="System Prompt V1 Test instructions.",
        few_shot_examples=[
            {"input": "Hi double payment", "expected_output": {"category": "billing", "summary": "Double payment query."}}
        ]
    )

@pytest.fixture
def mock_prompt_config_v2() -> PromptConfig:
    return PromptConfig(
        version="2.0.0",
        timestamp="2026-06-12T10:15:00Z",
        model="gpt-4o-mini",
        temperature=0.1,
        system_prompt="System Prompt V2 instructions.",
        few_shot_examples=[]
    )
