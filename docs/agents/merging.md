# Merging

From an open pull request to a merged, deployed release. What CI runs is in the README ("Tests")
and `ship.md`; this file holds the steps around a merge and what has gone wrong.

## Before merging

- **Bound every wait on checks.** A check can stay `pending` in `gh pr checks` (and `IN_PROGRESS` in
  `statusCheckRollup`) after its job finished, so `gh pr checks --watch` hangs. When the run reads
  `completed` and one check is still pending, read the job directly
  (`gh api repos/jwh3times/TirelessInvest/actions/jobs/<id>`): merge when it has a `conclusion` of
  success and the PR's `mergeStateStatus` is `CLEAN`.
- **`BLOCKED` with every check green is usually a new CodeQL alert.** The `main` ruleset blocks a
  merge on any new alert (errors and warnings, or medium security severity and up), and neither
  `gh pr view` nor GraphQL says why. Query the PR's head ref, not its merge ref:
  `gh api "repos/jwh3times/TirelessInvest/code-scanning/alerts?ref=refs/pull/<N>/head&state=open"`,
  and read the `CodeQL` check run's summary ("1 new alert…"). A new workflow job needs an explicit
  `permissions:` block, or it raises `actions/missing-workflow-permissions`.

## Merging several PRs

`main` requires branches up to date, and auto-merge is disabled for the repository (`--auto` is
refused). Once one PR merges, the next shows `BEHIND`: `gh pr update-branch <n>`, poll
`mergeStateStatus` until `CLEAN` (about two minutes), then `gh pr merge <n> --merge`.

For a Dependabot PR, `update-branch` puts a merge commit by the maintainer at the branch tip, so the
`ship` changelog roll-up can't attribute that version to the bot. Commenting `@dependabot rebase`
instead keeps the bot as the author, but is slower.

## After the merge

**Check a migration reached production through Railway's logs**, not by querying the production
database. With the Railway MCP read tools: find the project and its `api` service, then read that
service's logs from just before the release workflow ran, filtered on `migration`. The pre-deploy
runner logs `INFO applied N migration(s): <versions>`. Railway tags that line `severity: error`
because Python logging writes to stderr; a real failure logs `migration failed:` and fails the
deploy ([ADR 0001](../adr/0001-railway-applies-migrations-at-deploy.md)).

## Editing `CHANGELOG.md`

The file isn't valid UTF-8 on purpose: the 0.1.0 footer example (`v0.1.0 · <short commit>`) is a
single Latin-1 byte, `0xB7`, which an earlier UTF-8 rewrite broke. Some editors refuse the file, and
a rewrite as UTF-8 breaks the byte again. Insert a section with a byte-level edit that keeps that
byte, then check that `git diff -U0 CHANGELOG.md` shows no removed lines and run
`node scripts/check-changelog.mjs`. On a Windows checkout the working copy has CRLF endings, so a
byte-level anchor must use `\r\n`.
