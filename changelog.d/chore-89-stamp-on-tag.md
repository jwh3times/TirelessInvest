### Changed

- **Each merge's changelog section is now stamped after it lands** (#89). A branch writes its
  entries to its own `changelog.d/<branch-slug>.md` fragment and never edits `CHANGELOG.md`; after
  the merge, the release workflow turns the fragment, or the PR title when there is none, into the
  dated section, tags the merge commit, and creates a GitHub Release from the section. Pull
  requests no longer renumber their sections after each other's merges, and a Dependabot merge
  gets a section of its own instead of rolling up into the next one. The stamp commit is pushed by
  the release GitHub App, the `main` ruleset's one bypass actor. ADR 0003 records the move, and
  `docs/agents/releases.md`, `merging.md`, `ship.md`, the docs map, the README and
  `docs/INFRASTRUCTURE.md` describe it.
