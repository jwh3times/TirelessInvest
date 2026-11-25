### Fixed

- The deployment runbook now covers a deploy Railway itself fails while the code is fine.
  Railway does not retry it, so the API stays on the previous release and the release's `web` job
  fails its 15-minute wait. `docs/INFRASTRUCTURE.md` §11 gives the recovery: **Deploy Latest
  Commit** on `api` and `price-sync`, then re-run the failed `web` job. "Fix forward" now applies
  only to a deploy that fails on its code, in §8.2, `docs/agents/releases.md`,
  `docs/agents/merging.md` and the release workflow's comments.
- The docs no longer say the release's stamp commit never deploys. Railway's watch paths skip
  only push-triggered deploys: a deploy started by hand (**Deploy Latest Commit**, or applying a
  service setting change) builds `main`'s tip, often the stamp commit, and `/health` then reports
  it, harmlessly. `docs/INFRASTRUCTURE.md` §8.2 explains how to read its release, and
  `docs/agents/merging.md` now treats only a stamp-commit deploy not started by hand as lost
  watch paths. ADR 0003 carries a dated amendment, and the README says the web app deploys once the API
  reports the merge commit or a later one that contains it.
