# Each merge's changelog section is stamped after it lands

A branch writes its changelog entries to its own `changelog.d/<branch-slug>.md` fragment and never
edits `CHANGELOG.md`. After each merge to `main`, the release workflow runs
`scripts/stamp-changelog.mjs`, which turns that merge's fragments (or, when it added none, its PR
title) into a dated section for the version it mints. One `chore(release): v<x.y.z> [skip ci]`
commit adds the sections and deletes the fragments, the tag goes on the merge commit, and both are
pushed together with a token from the release GitHub App, the `main` ruleset's one bypass actor. A
GitHub Release is created from each section (`Scheme: stamp-on-tag` in `docs/agents/releases.md`,
the scheme the `jwh3times/skills` development flow shares).

## Considered options

- **Keep `per-merge`, where each branch writes the section for the version it predicts with
  `scripts/next-version.mjs`.** The prediction holds only for the branch that merges next. With
  several pull requests open, each claims the same version, so every merge sends the others back
  to renumber and re-run CI, and two sections inserted at the same place conflict. A Dependabot
  merge was exempt from the check and minted a tag with no section (`Skipped tags: roll up`), which
  the next section then had to cover.
- **Stamp from the release workflow with `GITHUB_TOKEN`.** The ruleset requires pull requests and
  status checks on `main`, and `GITHUB_TOKEN` cannot bypass a ruleset, so the stamp commit's push
  would be refused. The App adds a variable, a secret and a bypass actor, and is the only bypass.

## Consequences

- Pull requests merge in any order with no renumbering, and Dependabot's merges get a one-bullet
  section from their PR titles. The tags rolled up before the move (`v0.7.4`, `v0.7.5`, `v0.7.10`)
  keep no section; `v0.7.13` is on the last merge before it, so the move's own merge is the first
  one stamped.
- The required `changelog` check keeps its name. `node scripts/check-changelog.mjs` now fails a
  pull request that adds, removes or renumbers a version section, adds entries to `[Unreleased]`,
  edits or deletes a fragment already on `main`, or adds one that does not parse. It never requires
  a fragment.
- The tag job's stamps take turns in a concurrency group that never cancels a running stamp. A push
  rejected because `main` moved is not a failure: the run behind it stamps both merges, and its
  `web` job deploys a web app that contains the first. Only the newest merge's run deploys the web
  app then; the earlier run skips `web`.
- `main` moves twice per merge: the merge, then the stamp commit about a minute later. The ruleset
  requires branches to be up to date, so updating the next branch waits for the `Release` run.
- **Railway skips the stamp commit through watch paths.** Its docs describe no commit-message
  skip, so `[skip ci]` stops only GitHub Actions. Both services' watch paths are `**`,
  `!/CHANGELOG.md` and `!/changelog.d/**`: a change outside those paths still deploys, and the
  stamp commit, which touches only them, does not. Neither does a merge that touches only them, so
  its `web` job fails until the API is redeployed. `/health` reports the merge commit, the one the
  tag is on.
- (Corrected 2026-11-20: this record first expected Railway to deploy the stamp commit, harmlessly,
  since it is the merge's code and leaves no migration to apply
  ([ADR 0001](0001-railway-applies-migrations-at-deploy.md)). On `v0.7.14` it was not harmless.
  Railway started a deploy for the stamp commit 13 seconds after the merge's; the merge's deploy
  failed as it was superseded, and the stamp commit's failed too. The API stayed on the previous
  release for over 30 minutes, the `web` job timed out after 15, and a Railway redeploy and a
  re-run of the release run finished the release. The watch paths were added then.)
- Reopen this if releases stop following merges, if anything starts to act on the stamp commit (a
  tag-triggered workflow, a deployer that does not honor the watch paths), or if
  the App's access has to widen beyond pushing the stamp commit and tags.
