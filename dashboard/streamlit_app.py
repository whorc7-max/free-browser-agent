"""Small server-side dashboard for dispatching browser-agent jobs to GitHub."""

from __future__ import annotations

import re

import requests
import streamlit as st

MAX_TASK_LENGTH = 4_000
DEFAULT_TASK = "Open https://example.com and report the page title and heading."
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets[name]).strip()
    except KeyError:
        return default


def repository_url(repository: str) -> str:
    return f"https://github.com/{repository}"


def dispatch_task(repository: str, token: str, task: str, event_type: str) -> requests.Response:
    endpoint = f"https://api.github.com/repos/{repository}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "free-browser-agent-dashboard",
    }
    payload = {
        "event_type": event_type,
        "client_payload": {
            "task": task,
            "source": "streamlit-dashboard",
        },
    }
    return requests.post(endpoint, headers=headers, json=payload, timeout=20)


st.set_page_config(page_title="Browser Agent Control", page_icon="B", layout="centered")
st.title("Browser Agent Control")
st.caption("Write a task, then send it to a free GitHub Actions runner.")

repository = secret("GITHUB_REPOSITORY")
token = secret("GITHUB_TOKEN")
event_type = secret("GITHUB_EVENT_TYPE", "run-browser-agent")

if not repository or not token:
    st.error("Dashboard is not configured yet.")
    st.code(
        '[server]\n'
        'GITHUB_REPOSITORY = "owner/repository"\n'
        'GITHUB_TOKEN = "github_pat_..."\n'
        'GITHUB_EVENT_TYPE = "run-browser-agent"',
        language="toml",
    )
    st.info("Add these values to Streamlit Secrets. The token stays on the server and is never shown in the page.")
    st.stop()

if not REPOSITORY_PATTERN.fullmatch(repository):
    st.error("GITHUB_REPOSITORY must look like owner/repository.")
    st.stop()

task = st.text_area(
    "What should the browser do?",
    value=DEFAULT_TASK,
    height=160,
    max_chars=MAX_TASK_LENGTH,
    placeholder="Example: Open a public page, find the latest article title, and return its URL.",
)
st.caption(f"{len(task)}/{MAX_TASK_LENGTH} characters")

if st.button("Run browser task", type="primary", use_container_width=True):
    clean_task = task.strip()
    if not clean_task:
        st.warning("Enter a task first.")
    elif len(clean_task) > MAX_TASK_LENGTH:
        st.warning(f"Keep the task under {MAX_TASK_LENGTH} characters.")
    else:
        with st.spinner("Sending task to GitHub Actions..."):
            try:
                response = dispatch_task(repository, token, clean_task, event_type)
            except requests.RequestException:
                st.error("GitHub could not be reached. Try again in a moment.")
            else:
                if response.status_code == 204:
                    st.success("Task accepted. Open the Actions page to watch the run and download its result.")
                    st.link_button("Open GitHub Actions", f"{repository_url(repository)}/actions")
                elif response.status_code in {401, 403}:
                    st.error("GitHub rejected the token. Check its repository permissions and expiration.")
                elif response.status_code == 404:
                    st.error("Repository not found. Check GITHUB_REPOSITORY and token access.")
                else:
                    st.error(f"GitHub returned HTTP {response.status_code}. Check the repository settings.")
