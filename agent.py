"""Run a browser-use task with Gemini 2.5 Flash.

The script is intentionally small: GitHub Actions supplies AGENT_TASK and
GEMINI_API_KEY, while local runs can use a .env file or --task.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_TASK = """
Open https://example.com. Read the page title and the main heading. Confirm
that the title is 'Example Domain', then return a short success message with
the title, heading, and final URL. Do not navigate to another website.
""".strip()
MAX_TASK_LENGTH = 4_000


def get_task() -> str:
    parser = argparse.ArgumentParser(description="Run one browser-use task with Gemini.")
    parser.add_argument("--task", help="The browser task to run.")
    parser.add_argument(
        "--playwright-smoke-test",
        action="store_true",
        help="Verify that the Playwright Chromium binary can launch before the agent starts.",
    )
    args = parser.parse_args()

    task = (args.task or os.getenv("AGENT_TASK") or DEFAULT_TASK).strip()
    if not task:
        raise ValueError("Task is empty. Set AGENT_TASK or pass --task.")
    if len(task) > MAX_TASK_LENGTH:
        raise ValueError(f"Task is too long. Use at most {MAX_TASK_LENGTH} characters.")

    # Pass this flag through without adding another global variable.
    os.environ["RUN_PLAYWRIGHT_SMOKE_TEST"] = "1" if args.playwright_smoke_test else os.getenv(
        "RUN_PLAYWRIGHT_SMOKE_TEST", "0"
    )
    return task


async def playwright_smoke_test() -> None:
    """Confirm the browser binary installed by `playwright install` is usable."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto("https://example.com", wait_until="domcontentloaded", timeout=30_000)
            title = await page.title()
        finally:
            await browser.close()

    if title != "Example Domain":
        raise RuntimeError(f"Playwright smoke test saw unexpected title: {title!r}")
    print("Playwright smoke test passed: Example Domain")


def write_result(result: dict) -> None:
    result_path = Path(os.getenv("AGENT_RESULT_PATH", "agent_result.json"))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


async def run_agent(task: str) -> dict:
    from browser_use import Agent, ChatGoogle

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it as a local environment variable or GitHub Secret.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    llm = ChatGoogle(
        model=model,
        api_key=api_key,
        temperature=0.2,
        thinking_budget=0,
        max_output_tokens=4_096,
    )
    agent = Agent(
        task=task,
        llm=llm,
        use_vision=True,
        max_actions_per_step=3,
        max_failures=3,
        use_judge=True,
    )
    history = await agent.run(max_steps=int(os.getenv("AGENT_MAX_STEPS", "25")))
    success = history.is_successful() is True
    final_result = history.final_result()

    return {
        "success": success,
        "model": model,
        "task": task,
        "final_result": final_result,
        "steps": len(history),
        "urls": history.urls(),
        "errors": history.errors(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


async def main() -> int:
    try:
        task = get_task()
        if os.getenv("RUN_PLAYWRIGHT_SMOKE_TEST", "0").lower() in {"1", "true", "yes"}:
            await playwright_smoke_test()

        result = await run_agent(task)
        write_result(result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["success"] else 1
    except Exception as exc:
        error = {
            "success": False,
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_result(error)
        print(json.dumps(error, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
