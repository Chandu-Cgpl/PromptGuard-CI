import os
import time
import json
import asyncio
from typing import Dict, Any, Optional
import litellm
from src.config import PromptConfig, ClassifierOutput

# Check if we should run in Mock mode
keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "COHERE_API_KEY", "GROQ_API_KEY"]
HAS_KEY = any(os.getenv(k, "").strip() for k in keys)
IS_MOCK = not HAS_KEY or os.getenv("OPENAI_API_KEY", "").lower().startswith("mock")

# In mock mode, we want to simulate prompt-specific behavior to show regressions.
# v1.0.0 = High quality, handles edge cases.
# v2.0.0 = Poor quality, fails on sarcasm, mixed categories, or double requests.
def get_mock_response(email_text: str, version: str) -> Dict[str, Any]:
    text_lower = email_text.lower()
    
    # 1. Default classification logic (v1.0.0 - smart parsing)
    if "charge" in text_lower or "invoice" in text_lower or "refund" in text_lower or "billing" in text_lower or "card" in text_lower or "pricing" in text_lower or "double payment" in text_lower or "pay" in text_lower:
        category = "billing"
        summary = "Customer inquiries about billing, payment issues, or refund requests."
    elif "bug" in text_lower or "crash" in text_lower or "error" in text_lower or "login" in text_lower or "slow" in text_lower or "down" in text_lower or "api" in text_lower or "broken" in text_lower or "glitch" in text_lower:
        category = "technical"
        summary = "Customer reports login failure, software bugs, or API service issues."
    elif "password" in text_lower or "reset" in text_lower or "account" in text_lower or "profile" in text_lower or "delete" in text_lower or "upgrade" in text_lower or "permission" in text_lower or "username" in text_lower:
        category = "account"
        summary = "Customer requests account access modifications, deletion, or settings updates."
    else:
        category = "general"
        summary = "Customer provides general feedback or inquiries about the system."

    # 2. Simulate prompt-based quality regressions in v2.0.0
    if version == "2.0.0":
        # Regression 1: Misclassify sarcasm or complex double-intent.
        # If email contains sarcastic or compound feedback like "My login works but the double billing is amazing!",
        # v1.0.0 would prioritize 'billing' or identify the core problem.
        # v2.0.0 fails and defaults to 'technical' or 'general' because of lack of rules.
        if "billing is amazing" in text_lower or "sarcasm" in text_lower or "love getting double billed" in text_lower:
            category = "general" # Misclassification
            summary = "Customer is happy with the billing system." # Sarcastic misinterpretation
        elif "login" in text_lower and "charge" in text_lower:
            category = "technical" # Ambiguous choice regression
            summary = "Customer reports login issues and a billing charge."
        elif "typo" in text_lower or "glitchy" in text_lower:
            category = "general" # Fails on typo edge case
            summary = "Customer email containing typo details."
        else:
            # General summary degradation in v2.0.0 (less detailed, contains pleasantries, or too wordy)
            summary = f"Summary: Customer is contacting support regarding an issue which seems to be about the category of {category} and needs help."

        # Make summary longer than 15 words to violate guidelines
        if len(summary.split()) > 15:
            summary = summary[:80]
            
    # Mock token usage
    input_tokens = len(email_text.split()) + 50
    output_tokens = len(summary.split()) + 10
    
    return {
        "category": category,
        "summary": summary,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

async def classify_email(
    email_text: str, 
    config: PromptConfig, 
    client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Classifies a customer support email based on a PromptConfig.
    Returns a dictionary containing:
      - category (str)
      - summary (str)
      - input_tokens (int)
      - output_tokens (int)
      - latency (float)
      - error (str, optional)
    """
    start_time = time.time()
    
    if IS_MOCK:
        # Simulate network latency
        await asyncio.sleep(0.05)
        latency = time.time() - start_time
        mock_data = get_mock_response(email_text, config.version)
        return {
            "category": mock_data["category"],
            "summary": mock_data["summary"],
            "input_tokens": mock_data["input_tokens"],
            "output_tokens": mock_data["output_tokens"],
            "latency": latency,
            "error": None
        }
    
    try:
        # Add few-shot examples if present in the prompt config
        messages = [{"role": "system", "content": config.system_prompt}]
        for example in config.few_shot_examples:
            messages.append({"role": "user", "content": example["input"]})
            messages.append({"role": "assistant", "content": json.dumps(example["expected_output"])})
            
        messages.append({"role": "user", "content": email_text})
        
        # Use LiteLLM acompletion
        response = await litellm.acompletion(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            response_format=ClassifierOutput,
            max_tokens=250
        )
        
        latency = time.time() - start_time
        
        # Safely parse content string
        content_str = response.choices[0].message.content or ""
        if content_str.startswith("```json"):
            content_str = content_str[7:]
        if content_str.endswith("```"):
            content_str = content_str[:-3]
        content_str = content_str.strip()
        
        parsed_output = ClassifierOutput.model_validate_json(content_str)
        usage = response.usage
        
        return {
            "category": parsed_output.category,
            "summary": parsed_output.summary,
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "latency": latency,
            "error": None
        }
        
    except Exception as e:
        latency = time.time() - start_time
        return {
            "category": "general",
            "summary": "Error occurred during classification.",
            "input_tokens": 0,
            "output_tokens": 0,
            "latency": latency,
            "error": str(e)
        }
