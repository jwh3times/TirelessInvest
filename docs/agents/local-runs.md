# Local runs

Traps when running the API, the web build and the tests on a development machine, most of them seen
on the maintainer's Windows machine. The commands are in `AGENTS.md` and the README.

## Toolchain

- **`uv` installed with winget isn't on Git Bash's `PATH`.** Prepend its folder under
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*`.
- **`pnpm` may not be installed, and Node 26 has no Corepack.** `npx -y pnpm@10 <command>` runs the
  same major CI pins. The Supabase CLI isn't on `PATH` either: after `npx -y pnpm@10 install` at the
  repository root, run it as `npx -y pnpm@10 exec supabase <command>`.

## Tests

- **Without `TEST_DATABASE_URL` the integration tests skip silently.** The README's form points it
  at the local Supabase stack. With no stack, a throwaway Postgres container works:

  ```bash
  docker run -d --name ti-test-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:17
  TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55432/postgres uv run pytest -q
  ```

  Keep the container between runs (`docker start ti-test-pg`, `docker stop ti-test-pg`), and check
  `docker start` succeeded before running pytest: with the variable set and nothing listening,
  pytest hangs connecting instead of failing.

## The web build

- **Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` and `VITE_API_URL` before a build check**, to
  CI's placeholders if nothing else. Without them `web/src/lib/supabase.ts` throws at module load
  and the bundler drops the whole app as unreachable, yet the build still "succeeds": a grep of the
  bundle finds nothing.
- **`web/tsconfig.tsbuildinfo` is tracked and every local build rewrites it.** Restore it before
  staging, or the commit carries build noise.

## Running against the local stack

- **Leave `SUPABASE_JWT_SECRET` unset** for a stack started by the pinned CLI (3.1.0). `supabase start`
  prints a `JWT_SECRET`, but the CLI signs user tokens with ES256, so setting it makes the API reject
  every token with "The specified alg value is not allowed" (401). The README's legacy-secret case is
  a project still on a shared HS256 secret.
- **Environment variables can be passed inline** to `uvicorn` and `pnpm dev` instead of writing env
  files.
- **Invitation emails land in Mailpit** at <http://127.0.0.1:54324>; its
  `/api/v1/search?query=to:<email>` and `/api/v1/message/<id>` endpoints return the link.
- `supabase stop` without `--no-backup` keeps the local data.

## Scripts that read values

In Git Bash on Windows, `jq -r` and `python -c 'print(...)'` end lines with `\r\n`, and `read` keeps
the `\r`. A deploy wizard that reloaded its values that way saved a `\r` into a database password,
which reached `DATABASE_URL` as `%0D` and tripped the pooler's lockout. Strip it (`"${v//$'\r'/}"`)
from every value read from `jq`, `python` or `op` output before using or saving it.
