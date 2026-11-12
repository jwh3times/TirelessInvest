# Railway applies migrations at deploy, with Wait for CI off

Production schema migrations run as a Railway pre-deploy step on both the `api` and `price-sync`
services, using the database URL Railway already holds. Railway's "Wait for CI" is off, and the web
app deploys from a GitHub Actions release workflow only after `/health` reports the merge commit.
This gives the order migrate, then API, then web, and keeps the production database credential out
of GitHub.

## Considered options

- **Migrate from GitHub Actions and let Wait for CI hold Railway's deploy until it succeeds.** This
  is the obvious design, and it deadlocks. Wait for CI holds a deploy until every workflow run on
  the commit has finished, and a workflow that then waits for the API to go live never finishes.
  Railway skips the deploy after two hours. Railway's GitHub deployment statuses go from
  `in_progress` to `inactive`, never `success`, so there is no clean event to chain a second
  workflow on, and a chained workflow would race the same gate.
- **Drive Railway deploys from Actions through its API.** This gives full control, but it puts a
  Railway token and the database credential in CI. Railway's docs do not say whether a project
  token may deploy a given commit.

## Consequences

- Wait for CI is redundant here, because the `main` ruleset already requires every CI check to pass
  on an up-to-date branch before a merge.
- Railway builds from the repository root so that the image holds `supabase/migrations/`.
- Migrations stay additive, and the runner tolerates migrations it does not know. An emergency
  Railway rollback deploys an older image against a newer schema.
- Nobody runs `supabase db push` against production after first-time setup.
