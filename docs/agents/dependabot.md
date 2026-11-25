# Dependabot

What reviewing a Dependabot pull request takes here, read by the `dependabot` skill in a session
and in the scheduled review. These facts apply to this repository only.

## Stack

- **API** (`api/`): FastAPI and uvicorn, pydantic and pydantic-settings, a pandas and numpy
  backtesting engine (`api/src/tirelessinvest/engine/`), an httpx client for Alpaca market data
  (`market/alpaca.py`), psycopg 3 with `psycopg_pool`, and pyjwt. It is managed with uv
  (`api/pyproject.toml`, `api/uv.lock`), linted and formatted with ruff, and tested with pytest.
- **Image:** one `api/Dockerfile` (`FROM python:3.15-slim`, with uv copied in from
  `ghcr.io/astral-sh/uv:0.11.32`), which Railway builds and runs as two services, the API and the
  price-sync cron job. The image carries `supabase/migrations/`, and its pre-deploy step applies
  them ([ADR 0001](../adr/0001-railway-applies-migrations-at-deploy.md)). The database is the one
  hosted Supabase project.
- **Web** (`web/`): a React 19 SPA on Vite 8 and TypeScript 7, with react-router-dom 7,
  @tanstack/react-query, recharts and @supabase/supabase-js, installed with pnpm from
  `web/pnpm-lock.yaml`. `release.yml` builds it and deploys it to Cloudflare Pages.
- **Root** `package.json`: it only pins the Supabase CLI (`supabase` 3.2.0) for the local stack,
  with its own `pnpm-lock.yaml`.

`.github/workflows/ci.yml` runs four jobs, all required on `main`: `api` (a `postgres:17` service,
then `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .` and
`uv run pytest -q` with `TEST_DATABASE_URL` set, in `api/`), `web` (`pnpm install
--frozen-lockfile` and `pnpm build` in `web/`, with placeholder `VITE_*` values), `changelog`
(`node scripts/check-changelog.mjs`) and `agents` (the repository scripts on Node 22, among them
"API Python matches the Dockerfile", `node scripts/check-python-version.mjs`). `release.yml` runs
on a push to `main`: its `tag` job stamps the changelog and tags the merge, and its `web` job
deploys the web app after the API reports the merge commit or a later one that contains it.

`.github/dependabot.yml` opens updates daily; one review covers a grouped PR:

- **uv, `/api`:** `python-minor-and-patch` groups minor and patch updates; each major is its own PR.
- **npm, `/web`:** `react` (majors of react, react-dom, @types/react and @types/react-dom), `vite`
  (majors of vite and @vitejs/plugin-react), and `npm-minor-and-patch`.
- **npm, `/`:** the Supabase CLI, one PR per version, majors included.
- **docker, `/api`:** the API image's base.
- **github-actions, `/`:** `actions-minor-and-patch`; each major is its own PR.

## Review triggers

- **The `python` base image in `api/Dockerfile`, on any bump that changes `major.minor`** (3.15 to
  3.16). The Docker tag makes it look like a minor bump, but it is a new Python release that
  production runs, and it is red in CI until `api/.python-version` moves with it (Grounding facts).

## Resolution

- **Toolchain.** Node 22 and pnpm 10. No `.nvmrc` or `packageManager` names them: every
  `actions/setup-node` step in `ci.yml` and `release.yml` pins `node-version: 22`, and
  `pnpm/action-setup` pins `version: 10`. Under Node 22, `npm install -g pnpm@10`, or run
  `npx -y pnpm@10 <command>` (`docs/agents/local-runs.md`). Python 3.15, from `api/.python-version`:
  CI's `astral-sh/setup-uv` step has no `python-version` input, so uv reads that file. If
  `uv python find 3.15` fails, run `uv python install 3.15`.
- **uv** (`api/pyproject.toml`, `api/uv.lock`), from `api/`: `uv lock --check`, then
  `uv sync --frozen`.
- **web** (`web/package.json`, `web/pnpm-lock.yaml`), from `web/`: `pnpm install --frozen-lockfile`,
  reading the unmet-peer lines against `main`.
- **root** (`package.json`, `pnpm-lock.yaml`, the Supabase CLI), from the repository root:
  `pnpm install --frozen-lockfile`.
- **docker** (`api/Dockerfile`): no lockfile. Run `node scripts/check-python-version.mjs` at the
  repository root.

## Where to look

- `api/src/tirelessinvest/`: `engine/` (pandas, numpy), `market/` (httpx, pandas), `routes/` and
  `main.py` (fastapi), `config.py` (pydantic-settings), `db.py` (psycopg, psycopg_pool), `auth.py`
  (pyjwt, `fastapi.security`) and `jobs/` (the migration runner and price sync).
- `api/tests/`: Starlette's TestClient, and `httpx.MockTransport` in `test_alpaca.py`.
- The `[tool.pytest.ini_options]` and `[tool.ruff]` sections of `api/pyproject.toml`.
- `api/Dockerfile`, which pins two images: the `python` base and the `ghcr.io/astral-sh/uv` image
  it copies uv from.
- `supabase/config.toml`, for a Supabase CLI bump.
- `web/vite.config.ts`, `web/tsconfig.json` and `web/src/`.
- The `with:` inputs in `ci.yml` and `release.yml`.

## Grounding facts

- **Dependabot bumps the Python version only in `api/Dockerfile`.** The `agents` job's "API Python
  matches the Dockerfile" step fails until `api/.python-version` names the same `major.minor`, with
  `API Python mismatch: api/Dockerfile runs <new>, api/.python-version pins <old>`
  (`scripts/check-python-version.mjs`, `docs/INFRASTRUCTURE.md` §8.1). A red check there on a
  docker PR is the designed outcome, not a flake: NEEDS EFFORT, quoting that line, with the
  Playbook fix.
- **Starlette deprecations are errors.** `api/pyproject.toml` sets
  `filterwarnings = ["error::starlette.exceptions.StarletteDeprecationWarning"]`, so a fastapi or
  starlette bump that deprecates something the code or the tests use fails pytest by design; quote
  the warning that became an error.
- **httpx is a runtime dependency; httpx2 is a test one.** httpx is the Alpaca client's transport
  (`market/alpaca.py`, used by the price-sync job), covered by `api/tests/test_alpaca.py`. httpx2,
  in the `dev` dependency group, is what Starlette's TestClient runs on, so an httpx2 bump changes
  test infrastructure only. pytest is the gate for both.
- **The `postgres:17` service in CI is a throwaway test database.** Production is the hosted
  Supabase project, and no Postgres image is deployed, so a Postgres data-directory hazard does not
  apply here.
- **The changelog check says nothing about the dependency.** CI runs `check-changelog.mjs` with no
  `--source`, so a branch that adds no `changelog.d/` fragment, as a Dependabot branch does, passes
  it. At release, `scripts/stamp-changelog.mjs` writes that merge's entry under `Changed` from its
  PR title (`release.yml`, `docs/agents/releases.md`).
- **@vitejs/plugin-react needs a matching Vite major**, which is why the `vite` group exists
  (`.github/dependabot.yml`). Review it as one unit.
- **The root Supabase CLI pin is for the local stack only.** No CI job installs it, and production
  migrations are applied by the API image's pre-deploy step, not by the CLI.

## Playbook

- **Python library major** (pandas, numpy, pydantic, pydantic-settings, fastapi, uvicorn, psycopg,
  pyjwt, httpx, httpx2, pytest): read the migration guide for every major crossed, and search
  `api/src/tirelessinvest/` for the APIs used (Where to look). Gates, from `api/`: the Resolution
  commands, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -q`. Without
  `TEST_DATABASE_URL`, `api/tests/conftest.py` skips the tests that need a database: say so in the
  comment, and that CI's `api` job runs them against `postgres:17`.
- **ruff bump:** rule and formatter changes can turn CI red. Run `uv run ruff check .` and
  `uv run ruff format --check .`, and cite the rule or style change against `[tool.ruff]`
  (`select = ["E", "F", "I", "B", "UP", "SIM"]`, `target-version = "py312"`).
- **Python base image** (`major.minor` change): CI's `agents` job is red by design (Grounding
  facts). The fix: set `api/.python-version` to the new `major.minor` in the same PR, then
  `node scripts/check-python-version.mjs` passes, and CI's `api` job (`uv sync --frozen` and
  pytest on the new Python) is the gate.
- **web `react` or `vite` group major:** run `pnpm install --frozen-lockfile` and the build from
  `web/`, `VITE_SUPABASE_URL=http://127.0.0.1:54321 VITE_SUPABASE_ANON_KEY=ci-placeholder
  VITE_API_URL=http://127.0.0.1:8000 pnpm build` (`tsc -b && vite build`, with `ci.yml`'s
  placeholder values). Compare the unmet-peer lines against `main`: react-router-dom,
  @tanstack/react-query and recharts on a react major; @vitejs/plugin-react on a vite major.
- **Supabase CLI (root):** local stack only. Read the release notes for changes to
  `supabase/config.toml` keys or `supabase start` behaviour, and run the root
  `pnpm install --frozen-lockfile`.
- **GitHub Actions major:** NEEDS EFFORT only when a removed or renamed input, or a changed default,
  reaches a `with:` input; name the step. The inputs in use: `actions/checkout` (`fetch-depth: 0`,
  `ref: main`, `token`), `actions/setup-node` (`node-version: 22`, `cache: pnpm`,
  `cache-dependency-path: web/pnpm-lock.yaml`), `pnpm/action-setup` (`version: 10`),
  `astral-sh/setup-uv` (none: it must keep letting uv read `api/.python-version`),
  `actions/create-github-app-token` (`client-id`, `private-key`, `permission-contents: write`) and
  `1password/load-secrets-action` (`export-env: true`).
