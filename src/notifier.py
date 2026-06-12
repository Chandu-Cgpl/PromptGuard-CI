import os
import json
import urllib.request
from typing import Dict, Any, Optional
from src.config import EvalRun

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()

def send_slack_alert(
    run: EvalRun,
    status: str,
    diff: Dict[str, Any],
    report_path: str,
    drift_info: Optional[Dict[str, Any]] = None,
    baseline: Optional[EvalRun] = None
) -> Dict[str, Any]:
    """
    Constructs a rich Slack Block Kit notification and posts it.
    If SLACK_WEBHOOK_URL is missing, saves the JSON payload to reports/.
    """
    # 1. Choose color/emoji based on status
    if status == "CRITICAL":
        status_emoji = "🔴"
        status_text = "CRITICAL REGRESSION DETECTED"
        color_bar = "#ef4444"
    elif status == "WARNING":
        status_emoji = "⚠️"
        status_text = "WARNING: REGRESSION DETECTED"
        color_bar = "#f59e0b"
    else:
        status_emoji = "🟢"
        status_text = "EVALUATION PASSED SUCCESSFULLY"
        color_bar = "#10b981"

    # 2. Extract metrics and deltas
    reg_count = len(diff.get("regressions", []))
    imp_count = len(diff.get("improvements", []))
    
    accuracy_text = f"*{run.pass_rate:.1f}%*"
    relevance_text = f"*{run.avg_relevance:.2f}/5*"
    
    if baseline:
        acc_delta = run.pass_rate - baseline.pass_rate
        rel_delta = run.avg_relevance - baseline.avg_relevance
        
        acc_sign = "+" if acc_delta > 0 else ""
        rel_sign = "+" if rel_delta > 0 else ""
        
        accuracy_text += f" ({acc_sign}{acc_delta:.1f}% vs baseline)"
        relevance_text += f" ({rel_sign}{rel_delta:.2f} vs baseline)"

    # 3. Build Block Kit blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_emoji} LLM Evaluation: {status_text}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Prompt Version:* `v{run.prompt_version}`"},
                {"type": "mrkdwn", "text": f"*Model:* `{run.model}`"},
                {"type": "mrkdwn", "text": f"*Run ID:* `{run.id}`"},
                {"type": "mrkdwn", "text": f"*Scored Cases:* `{run.total_cases}`"}
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Category Accuracy:*\n{accuracy_text}"},
                {"type": "mrkdwn", "text": f"*Summary Relevance:*\n{relevance_text}"},
                {"type": "mrkdwn", "text": f"*Regressions:*\n*{reg_count} cases*"},
                {"type": "mrkdwn", "text": f"*Improvements:*\n*{imp_count} cases*"}
            ]
        }
    ]

    # Add Drift warning to Slack if present
    if drift_info and drift_info.get("drift_detected"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *Performance Drift Alert:*\n{drift_info['message']}"
            }
        })

    # Add details of regressed case IDs if they exist
    if reg_count > 0:
        reg_ids = [r["case_id"] for r in diff["regressions"]]
        # Limit display size to avoid block limit overflow
        if len(reg_ids) > 10:
            reg_list = ", ".join(reg_ids[:10]) + f" ...and {len(reg_ids)-10} more"
        else:
            reg_list = ", ".join(reg_ids)
            
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *Regressed Cases:* {reg_list}"
            }
        })

    # Add report location links/action buttons
    blocks.append({
        "type": "divider"
    })
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"📂 *HTML Diagnostic Report Generated:*\n`{report_path}`"
        }
    })

    # Wrap in Slack attachment for colored side-bar
    payload = {
        "attachments": [
            {
                "color": color_bar,
                "blocks": blocks
            }
        ]
    }

    # 4. Post Webhook or write locally
    if not SLACK_WEBHOOK_URL:
        # Dry-run / mock alerting mode
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        payload_file = os.path.join(reports_dir, f"slack_payload_{run.id}.json")
        with open(payload_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return {
            "sent": False,
            "saved_to": os.path.abspath(payload_file),
            "reason": "SLACK_WEBHOOK_URL is not set (mock mode)"
        }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            
        return {
            "sent": True,
            "response": res_body
        }
    except Exception as e:
        # Log error but don't crash the evaluator
        return {
            "sent": False,
            "error": str(e)
        }
