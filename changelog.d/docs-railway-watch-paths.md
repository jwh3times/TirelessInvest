### Fixed

- **A release no longer stalls on Railway's deploy of its changelog stamp commit.** Railway ignores
  `[skip ci]`, so on `v0.7.14` it deployed the stamp commit 13 seconds after the merge: the merge's
  deploy was superseded, the stamp commit's failed, the API stayed on the previous release for over
  30 minutes, and the web deploy timed out until a redeploy and a re-run. Both Railway services now
  set watch paths (`**`, `!/CHANGELOG.md`, `!/changelog.d/**`), so every change still deploys
  except a stamp commit. ADR 0003 carries a dated correction, and `docs/INFRASTRUCTURE.md`,
  `docs/agents/merging.md` and the release workflow's comments describe the watch paths.
