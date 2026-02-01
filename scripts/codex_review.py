"""
Codex Review Script

Calls OpenAI API to review fix-tasks.md and replace Codex Commentary section.
Part of the overnight automation workflow.

Usage:
    python scripts/codex_review.py

Requires:
    OPENAI_API_KEY in .env file or environment variable
"""

import os
import sys
import time
from datetime import datetime

# Load .env file
from dotenv import load_dotenv
load_dotenv()

try:
    from openai import OpenAI
    from openai import RateLimitError, APIError
except ImportError:
    print("ERROR: openai package not installed. Run: pip install openai")
    sys.exit(1)

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # Initial delay, doubles each retry


ARTIFACTS_DIR = "artifacts"
FIX_TASKS_FILE = os.path.join(ARTIFACTS_DIR, "fix-tasks.md")

# Cost control settings
# gpt-4-turbo pricing: $10/1M input, $30/1M output tokens
INPUT_COST_PER_TOKEN = 0.00001   # $10 / 1M
OUTPUT_COST_PER_TOKEN = 0.00003  # $30 / 1M
MAX_COST_USD = 1.00  # Hard cap - fail if estimated cost exceeds this
MAX_INPUT_TOKENS = 50000  # Pre-flight check - fail if prompt too large

REVIEW_PROMPT = """You are reviewing proposed code fixes for a Python/FastAPI news aggregation app.

## Proposed Fixes

{fix_tasks_content}

## Your Review

For each fix:
1. **Verdict**: APPROVE / NEEDS CHANGE / REJECT
2. **Code pattern**: Show exact code if proposal is vague
3. **Edge cases**: What could break?

Also note any fixes that are wrong, unnecessary, or missing.

If there are no critical or medium priority fixes proposed, simply respond:
"## Codex Commentary

No critical or medium fixes to review. Codebase looks clean."

Format as markdown starting with "## Codex Commentary"
"""


def main():
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Read fix-tasks.md
    if not os.path.exists(FIX_TASKS_FILE):
        print(f"ERROR: {FIX_TASKS_FILE} not found")
        sys.exit(1)

    with open(FIX_TASKS_FILE, "r", encoding="utf-8") as f:
        fix_tasks_content = f.read()

    # Strip existing Codex commentary if present (we'll replace it)
    # Check for multiple possible markers
    codex_markers = [
        "\n---\n\n*Codex review added:",
        "\n---\n\n## Codex Commentary",
        "\n## Codex Commentary",
    ]
    for marker in codex_markers:
        if marker in fix_tasks_content:
            fix_tasks_content = fix_tasks_content.split(marker)[0]
            print(f"Stripping existing Codex commentary (marker: {marker[:30]}...)")

    # Also strip Claude's Final Plan if present (comes after Codex)
    plan_markers = [
        "\n---\n\n## Claude's Final Plan",
        "\n## Claude's Final Plan",
    ]
    for marker in plan_markers:
        if marker in fix_tasks_content:
            fix_tasks_content = fix_tasks_content.split(marker)[0]

    # Pre-flight cost check: estimate input tokens (rough: 1 token ≈ 4 chars)
    prompt_content = REVIEW_PROMPT.format(fix_tasks_content=fix_tasks_content)
    estimated_input_tokens = len(prompt_content) // 4
    estimated_input_cost = estimated_input_tokens * INPUT_COST_PER_TOKEN

    print(f"Estimated input: ~{estimated_input_tokens:,} tokens (${estimated_input_cost:.4f})")

    if estimated_input_tokens > MAX_INPUT_TOKENS:
        print(f"ERROR: Prompt too large ({estimated_input_tokens:,} tokens > {MAX_INPUT_TOKENS:,} max)")
        print("Reduce fix-tasks.md size or increase MAX_INPUT_TOKENS")
        sys.exit(1)

    # Estimate max possible cost (input + max output)
    max_possible_cost = estimated_input_cost + (4000 * OUTPUT_COST_PER_TOKEN)
    if max_possible_cost > MAX_COST_USD:
        print(f"ERROR: Max possible cost ${max_possible_cost:.4f} exceeds cap ${MAX_COST_USD:.2f}")
        print("Reduce prompt size or increase MAX_COST_USD")
        sys.exit(1)

    print("Calling OpenAI API for Codex review...")

    # Call OpenAI API with retry/backoff for transient errors
    client = OpenAI(api_key=api_key)
    response = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": prompt_content
                    }
                ],
                temperature=0.2,
                max_tokens=4000
            )
            break  # Success, exit retry loop
        except RateLimitError:
            delay = RETRY_DELAY_SECONDS * (2 ** attempt)
            print(f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s...")
            time.sleep(delay)
        except APIError as e:
            if e.status_code in (500, 503):
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                print(f"API error {e.status_code} (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise  # Non-transient error, don't retry

    if response is None:
        print(f"ERROR: Failed after {MAX_RETRIES} retries")
        sys.exit(1)

    commentary = response.choices[0].message.content

    # Calculate actual cost (guard for missing usage)
    if response.usage:
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        actual_cost = (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
        print(f"Actual usage: {input_tokens:,} input + {output_tokens:,} output = {response.usage.total_tokens:,} total")
        print(f"Actual cost: ${actual_cost:.4f}")
        cost_footer = f"\n\n---\n*Cost: ${actual_cost:.4f} ({response.usage.total_tokens:,} tokens)*"
    else:
        print("Warning: Usage data not available")
        cost_footer = "\n\n---\n*Cost: unknown (usage data unavailable)*"

    # Write full content with new Codex commentary (replaces old)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(FIX_TASKS_FILE, "w", encoding="utf-8") as f:
        f.write(fix_tasks_content)
        f.write(f"\n---\n\n*Codex review added: {timestamp}*\n\n")
        f.write(commentary)
        f.write(cost_footer)

    print(f"Codex commentary written to {FIX_TASKS_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
