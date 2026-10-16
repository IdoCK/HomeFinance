# HomeFinance

This is the initial public release of HomeFinance following private development. The public snapshot contains the application, tests, example CSVs, build configuration, and user guide; internal planning notes and session history are outside its scope.

HomeFinance is a local household finance dashboard for turning bank, card, and shopping exports into a shared view of spending, budgets, savings goals, and net worth.

HomeFinance keeps the ledger in SQLite and provides individual and joint views. Its import workflow separates parsing, review, and saving so users can check categories, currencies, and transaction signs before entries affect the dashboard.

## What it does

- Imports CSV/TSV and Excel exports, with a Markdown registry of known statement layouts and optional local model inference for unfamiliar formats.
- Tracks transactions, category rules, vendor groups, budgets, recurring charges, and dated events.
- Compares spending across periods and household members, with category and vendor drill-downs.
- Tracks savings goals, asset and liability balances, balance history, and projections.
- Stores original currencies alongside a USD ledger base; supports USD/ILS display conversion and exchange-rate refreshes.
- Offers optional AI coaching with a preview of the application-generated summary.

The two seeded member names can be changed in Settings. Member views organize a shared local ledger; they are not separate authenticated accounts.

## Architecture

```text
Browser → React / TypeScript / Vite frontend (web/)
       → FastAPI JSON routes (backend/api/)
       → Python parsing, analytics, FX, and SQLite engine (modules/)
       → data/finance.db
```

FastAPI serves the built frontend from `web/dist`. During development, Vite proxies `/api` requests to the Python server. The older Streamlit interface remains in `app.py`; the React interface is the primary entry point. The portable [user guide](docs/USER_GUIDE.html) is included in `docs/`.

## Setup

You need Python with `venv`, Node.js and npm for building the frontend. Node is unnecessary for serving an already built frontend. Python dependencies are listed in `requirements.txt`; frontend dependencies have a lockfile in `web/package-lock.json`.

From the repository root:

```sh
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS / Linux
source .venv/bin/activate
```

Then install dependencies and build:

```sh
python -m pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
python run_api.py
```

Open [the local dashboard](http://127.0.0.1:8000). `run_api.py` starts a development server with reload enabled. Alternatively, `python run_app.py` opens the browser and selects another local port if 8000 is occupied; it installs/builds the frontend automatically when needed.

For frontend development, leave the API running and start Vite in another terminal:

```sh
npm --prefix web run dev
```

Open [the Vite frontend](http://localhost:5173). If `web/dist` does not exist, the API root redirects to its interactive API documentation.

## Import workflow

1. Select a member view and open Import.
2. Upload a bank, credit-card, or shopping export and select its source/currency as needed.
3. Review parsed rows, signs, categories, excluded transfers, and currency warnings.
4. Save the reviewed rows. Imports are tracked by file content hash per member.

Known layouts are parsed from [`csv_formats.md`](csv_formats.md) first. Unknown layouts use Ollama at `localhost:11434` with the default `qwen2.5` model. Set up Ollama separately, then download the model:

```sh
ollama pull qwen2.5
```

The local model receives sample file rows and, for categorization, merchant descriptions. It does not execute generated code. Review every unfamiliar format: inference can select incorrect columns or signs. The repository includes small example CSVs in `sample_data/`; they are not a substitute for checking your own exports.

## Privacy and security boundaries

The default API launchers bind to `127.0.0.1`. There is **no API authentication or authorization**, and the SQLite database is **not encrypted by the application**. Keep this service on a trusted local machine; exposing it to other users or a network requires additional access controls. The frontend member selector is a display filter, not an access-control boundary.

In a source checkout, the database is `data/finance.db`. Packaged builds store it in `data/` beside the executable. Back up that directory privately before updates or migrations. The database includes descriptions, member names, imported filenames, goals, and balances. Keep exports and backups out of version control; `.gitignore` covers the local data directory, environment files, and Streamlit secrets.

Optional network integrations have different data boundaries:

| Feature | Destination | Application-supplied information |
| --- | --- | --- |
| Unknown-format parsing / categorization | Local Ollama | Sample statement rows, filenames, descriptions, and category labels |
| Exchange-rate refresh | Frankfurter public API | Requested date and currency pair; no transaction amounts |
| AI insights | Installed Claude Code CLI and its configured provider | Category totals, savings statistics, goal names, horizons, progress, and monthly amounts needed |

AI insights use the `claude` command on PATH, optionally overridden by `CLAUDE_BIN`; this application's current implementation does not read `ANTHROPIC_API_KEY` directly. Configure the CLI separately. Without it, the payload preview remains available and live generation is disabled.

**The insights payload is not fully anonymous.** Member labels become generic and raw transaction descriptions and goal notes are omitted, but user-entered goal and category names can still identify people or sensitive topics. Review the preview before generating. The CLI inherits the local process environment, working directory, and its own configuration; the summary preview does not establish a sandbox or restrict any additional context the CLI may access. Existing in-app anonymity wording is stronger than these actual boundaries.

## Tests and builds

With the Python environment active:

```sh
python -m pytest -q
npm --prefix web test
npm --prefix web run build
npm --prefix web run lint
```

Tests cover engine calculations, migrations, API routes, import/currency handling, and frontend components. They use temporary databases and mocked integrations; passing them does not validate your bank's export or a live AI provider.

`python build.py` builds the frontend and bundles the application with PyInstaller using `HomeFinance.spec`. It may install missing build dependencies. The Windows output is `dist/HomeFinance.exe`. Packaging is separate from the test/build commands above and should be verified on the target platform.

## Current limitations

- This is a local, shared-household tool with no hosted multi-user security model.
- Parsing and categorization can be wrong; transfer exclusion, refund treatment, and reconciliation require review.
- Rates may be missing or stale. The app seeds a starter display rate; refresh or set it before relying on converted figures.
- Projections and AI coaching are estimates based on recorded data, not a financial planning guarantee.
- API uploads and model/CLI calls do not have a comprehensive application-level resource quota. Avoid untrusted clients and unexpectedly large imports.
- Python dependency versions are not locked. Reproducible Python installations and dependency security tracking need further work.
- The legacy Streamlit interface and user-guide privacy wording may lag the React implementation; use the data boundaries in this README when reviewing optional AI features.
