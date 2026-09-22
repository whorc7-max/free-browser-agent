# Free Browser Agent Starter

This is a small, no-paid-browser-cloud architecture:

```text
Streamlit dashboard
        | GitHub Repository Dispatch
        v
GitHub Actions (Ubuntu + Chromium + Python)
        | GEMINI_API_KEY secret
        v
browser-use Agent + Gemini 2.5 Flash vision/decision loop
        |
        v
agent_result.json + Actions artifact
```

The GitHub runner is ephemeral and headless. The dashboard never receives the
Gemini key and never sends the GitHub token to the browser page.

## Important Free-Tier Note

There is no paid Browser Use Cloud call in this starter. GitHub Actions,
Streamlit Community Cloud, and Google AI Studio may each have quotas or policy
limits that change over time. Public repositories generally have the most
generous GitHub Actions allowance. This is free within those quotas, not an
unlimited-service guarantee.

## Stage 1: GitHub Repository

1. Create a new GitHub repository. A public repository is simplest for free
   GitHub Actions usage.
2. Copy this starter's files into the repository root, preserving:
   `agent.py`, `requirements.txt`, and `.github/workflows/run_agent.yml`.
3. In Google AI Studio, create a Gemini API key. Keep it private.
4. In GitHub, open `Settings > Secrets and variables > Actions > New repository
   secret` and create:

   ```text
   Name: GEMINI_API_KEY
   Value: your Google AI Studio key
   ```

5. Commit and push the files to the repository's default branch, normally
   `main`.

The included `agent.py` uses the current browser-use Gemini adapter:

```python
llm = ChatGoogle(
    model="gemini-2.5-flash",
    api_key=os.environ["GEMINI_API_KEY"],
)
agent = Agent(task=task, llm=llm, use_vision=True)
history = await agent.run(max_steps=25)
```

The default task opens `https://example.com`, extracts the title and heading,
and returns a success result. Replace it through `AGENT_TASK` or the dashboard.

### Local test (optional)

Use Python 3.11 or newer. The key is loaded from `.env` and is never committed:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python agent.py --playwright-smoke-test
```

`langchain-google-genai` is included because it is part of the requested stack.
The current browser-use integration uses its native `ChatGoogle` adapter, so no
extra LangChain wrapper is needed for this example.

## Stage 2: GitHub Actions

The file `.github/workflows/run_agent.yml` supports both triggers:

- `workflow_dispatch`: use the **Run workflow** button in the Actions tab and
  enter a task.
- `repository_dispatch`: send a JSON request from the dashboard or another
  backend service.

The workflow installs Python 3.11, the pinned browser-use package, Playwright,
Chromium, and its Ubuntu dependencies. It passes the Gemini key only to the
runner process and uploads `agent_result.json` for seven days.

Manual trigger steps:

1. Open the repository's `Actions` tab.
2. Select `Run Browser Agent`.
3. Click `Run workflow`, enter a task, and start it.
4. Open the run after it finishes and download the `browser-agent-result-*`
   artifact.

### Repository Dispatch API

For a server-side caller, create a separate GitHub token with access only to
this repository. A fine-grained token needs repository `Contents: Read and
write` permission for repository dispatch. Then call:

```bash
curl --fail-with-body -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPOSITORY/dispatches \
  -d '{
    "event_type": "run-browser-agent",
    "client_payload": {
      "task": "Open https://example.com and report the page title."
    }
  }'
```

GitHub returns HTTP `204` when the event is accepted. The workflow file must
already exist on the repository's default branch for `repository_dispatch` to
run it.

## Stage 3: Streamlit Dashboard

The file `dashboard/streamlit_app.py` is a small control panel. It makes the
GitHub request from the Streamlit server, not from the visitor's browser.

### Run it locally

```bash
python -m venv .venv-dashboard
source .venv-dashboard/bin/activate       # Windows PowerShell equivalent works too
python -m pip install -r dashboard/requirements.txt
mkdir -p .streamlit
cp dashboard/secrets.example.toml .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with the repository and a restricted GitHub token.
streamlit run dashboard/streamlit_app.py
```

Never commit `.streamlit/secrets.toml`. The `.gitignore` already excludes it.

### Deploy free on Streamlit Community Cloud

1. Push the repository to GitHub.
2. Create a Streamlit Community Cloud app from that repository.
3. Set the main file to `dashboard/streamlit_app.py`.
4. In the app settings, open **Secrets** and paste:

   ```toml
   GITHUB_REPOSITORY = "OWNER/REPOSITORY"
   GITHUB_TOKEN = "github_pat_your_restricted_token"
   GITHUB_EVENT_TYPE = "run-browser-agent"
   ```

5. Deploy. Type a task and click **Run browser task**.

The dashboard does not need `GEMINI_API_KEY`; only GitHub Actions needs it.

## Safety And Limits

- Do not put API keys, passwords, cookies, or one-time codes in the repository,
  task text, workflow YAML, or screenshots.
- Do not give the agent access to private accounts unless you intentionally
  build a separate, audited login flow. This starter has no login storage.
- Treat dashboard users as trusted: a browser task can navigate to arbitrary
  websites and submit forms.
- Sites may block automation, require a login, or show different prices by
  country and account. That is normal browser behavior, not a workflow bug.
- Keep tasks short and specific to reduce Gemini calls and stay within free
  quotas.

## Troubleshooting

**`GEMINI_API_KEY is not set`**

Create the repository secret with exactly that name. For local runs, set it in
`.env`.

**Playwright cannot launch Chromium**

Run `python -m playwright install chromium` locally. The Actions workflow uses
`python -m playwright install --with-deps chromium`.

**Dashboard says GitHub rejected the token**

Check that `GITHUB_REPOSITORY` is `OWNER/REPOSITORY`, the token is not expired,
and the token has repository Contents write permission. Never paste the token
into the task box.

**The event is accepted but no run appears**

Confirm the workflow is on the default branch, Actions are enabled, and the
event type is exactly `run-browser-agent`.

