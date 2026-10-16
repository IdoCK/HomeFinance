# HomeFinance frontend

React 19 and TypeScript provide the browser interface, built with Vite. The app uses Tailwind, Radix UI, Recharts, and shared chart components. FastAPI provides the JSON API.

See the [project README](../README.md) for environment setup, data privacy, optional services, and packaging.

From the repository root:

```sh
npm --prefix web ci
npm --prefix web run dev
npm --prefix web test
npm --prefix web run build
npm --prefix web run lint
```

The development server listens on port 5173 and proxies `/api` to the local Python API on port 8000. Start the API separately with `python run_api.py`. A production frontend build writes `web/dist`, which FastAPI serves when present.

Component tests run with Vitest and React Testing Library. Tests do not call a live AI provider. The current code has existing lint failures and CSS build warnings; these are not resolved by the public snapshot preparation.
