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
  and read the `CodeQL` check run's summary ("1 new alert…"). A job with no `permissions:` of its
  own, in a workflow with no top-level block, raises `actions/missing-workflow-permissions`; both
  workflows set one, so a new workflow needs it too.

## Merging several PRs

`main` requires branches up to date, and auto-merge is disabled for the repository (`--auto` is
refused). Once one PR merges, the next shows `BEHIND`: `gh pr update-branch <n>`, poll
`mergeStateStatus` until `CLEAN` (about two minutes), then `gh pr merge <n> --merge`.

- **PRs merge in any order.** No branch names a version or edits `CHANGELOG.md`: each writes its
  own `changelog.d/<branch-slug>.md` fragment
  ([ADR 0003](../adr/0003-stamp-changelog-on-tag.md)), so open PRs don't collide over the changelog.
- **Wait for the stamp before updating the next branch.** About a minute after each merge, the
  release workflow's `tag` job pushes a `chore(release): v<x.y.z> [skip ci]` commit that moves
  `main` again. Run `gh pr update-branch` after that, or the branch needs a second update and a
  second CI run.

## After the merge

**Find the release run by commit.** Select the `Release` run whose `headSha` is the merge commit
(`gh run list --workflow release.yml --json databaseId,headSha,status,conclusion`); right after a
merge, `--limit 1` can return the previous one. Its `tag` job stamps the merge's section into
`CHANGELOG.md`, deletes its fragment, pushes the stamp commit as `release-stamper[bot]`, tags the
merge commit and creates the GitHub Release. Confirm with `git tag --points-at <merge commit>`: the
tag is on the merge, not on `main`'s new tip. A run whose stamp found `main` moved ends green with a
notice and skips `web`; the next merge's run releases both and deploys the web app.

**The stamp commit runs no workflow, but Railway deploys it.** Its `[skip ci]` keeps CI and
`Release` off it, so its CodeQL analysis is the only run it shows. Railway is expected to redeploy
`api` and `price-sync` from it, the same code with no migration left to apply, and `/health` then
reports the stamp commit (ADR 0003).

**Check a migration reached production through Railway's logs**, not by querying the production
database. With the Railway MCP read tools: find the project and its `api` service, then read that
service's logs from just before the release workflow ran, filtered on `migration`. The pre-deploy
runner logs `INFO applied N migration(s): <versions>`. Railway tags that line `severity: error`
because Python logging writes to stderr; a real failure logs `migration failed:` and fails the
deploy ([ADR 0001](../adr/0001-railway-applies-migrations-at-deploy.md)).

## `CHANGELOG.md`

No branch edits it: the release workflow stamps each merge's section, and the changelog check fails
a branch that adds, removes or renumbers a section. The file is UTF-8. Until 0.7.12 the 0.1.0
footer example held a lone Latin-1 middle dot (`0xB7`), so UTF-8 editors and tools refused the
file, and one rewrite turned it into a replacement character. If a tool refuses the file again, a
non-UTF-8 byte has come back: find it with `grep -naxv '.*' CHANGELOG.md` and fix it on a branch
of its own, instead of editing around it.
