from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PromptConfig(BaseModel):
    version: str
    timestamp: str
    model: str
    temperature: float
    system_prompt: str
    few_shot_examples: List[Dict[str, Any]] = []

class ClassifierOutput(BaseModel):
    category: str = Field(..., description="Must be one of: billing, technical, account, general")
    summary: str = Field(..., description="A concise, one-sentence summary of the user's issue (max 15 words).")

class TestCase(BaseModel):
    id: str
    input: str
    expected_category: str
    expected_summary: str
    expected_difficulty: str = "easy"  # easy, medium, hard
    notes: Optional[str] = None

class TestResult(BaseModel):
    case_id: str
    input_text: str
    expected_category: str
    expected_summary: str
    actual_category: str
    actual_summary: str
    category_passed: bool
    relevance_score: float  # 1.0 to 5.0
    latency: float
    input_tokens: int
    output_tokens: int
    error_message: Optional[str] = None

class EvalRun(BaseModel):
    id: str
    timestamp: str
    prompt_version: str
    model: str
    total_cases: int
    pass_rate: float
    avg_relevance: float
    avg_latency: float
    total_tokens: int
    total_cost: float
    config_hash: str
    is_baseline: bool = False
