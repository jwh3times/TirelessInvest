### Fixed

- **A release no longer stalls on Railway's deploy of its changelog stamp commit.** Railway ignores
  `[skip ci]`, so on `v0.7.14` it deployed the stamp commit 13 seconds after the merge: the merge's
  deploy was superseded, the stamp commit's failed, the API stayed on the previous release for over
  30 minutes, and the web deploy timed out until a redeploy and a re-run. Both Railway services now
  set watch paths (`**`, `!/CHANGELOG.md`, `!/changelog.d/**`): a stamp commit no longer deploys,
  and every push that changes anything else still does. ADR 0003 carries a dated correction, and
  `docs/INFRASTRUCTURE.md`, `docs/agents/merging.md` and the release workflow's comments describe
  the watch paths.
- **The runbook covers a merge that changes only the changelog files.** The watch paths skip it too,
  so the API never reports it and the release's `web` job fails. `docs/INFRASTRUCTURE.md` §11 gives
  the recovery: redeploy `api` in Railway, then re-run the failed `web` job.
