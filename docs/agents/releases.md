# Releases

## Scheme

stamp-on-tag — `.github/workflows/release.yml` tags every merge to `main`
`v<major>.<minor>.<build>` with a GitHub Release. Each branch's entries live in its own
`changelog.d/<branch-slug>.md` fragment; the workflow stamps them into the merge's dated section
and tags the merge commit (`changelog.d/README.md`;
[ADR 0003](../adr/0003-stamp-changelog-on-tag.md)). `Unreleased` stays an empty placeholder. The
tag is minted on merge, whether or not the deploy that follows succeeds; a failed deploy is fixed
forward.

## Version file

`VERSION` — the bare `<major>.<minor>.<build>` release line. It starts at `0.1.0`; `1.0.0` is cut
when the first invitee gets access.

## Ask before bumping

when ambiguous
