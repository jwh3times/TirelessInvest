# Releases

## Scheme

per-merge — `.github/workflows/release.yml` tags every merge to `main` `v<major>.<minor>.<build>`,
and each merge's dated changelog section names the version it mints. The tag is minted on merge,
whether or not the deploy that follows succeeds; a failed deploy is fixed forward.

## Skipped tags

roll up — a Dependabot merge is exempt from the changelog check and mints a tag with no section;
its changes fold into the next section written.

## Version file

`VERSION` — the bare `<major>.<minor>.<build>` release line. It starts at `0.1.0`; `1.0.0` is cut
when the first invitee gets access.

## Ask before bumping

when ambiguous
