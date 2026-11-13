# Changelog

All notable changes to TirelessInvest are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The product has
one version, the `vX.Y.Z` tag the release workflow puts on every merge to `main`; `VERSION` holds
the current release line as `X.Y.0`. Each section below names the version its merge minted. A Dependabot
merge mints a version with no section of its own: its changes are rolled up into the next section.
A major version means a breaking change for users (see `GLOSSARY.md`); until `1.0.0`, breaking
changes raise the minor version.

## [Unreleased]

No unreleased changes.


## [0.1.1] - 2026-11-12

### Changed

- `/what-next` puts an active handoff first: when `handoff_map.json` names one for this
  repository, the report leads with it and recommends `/lets-go`, and one whose document has not
  reached this machine is shown as pending. It still changes nothing, and a machine without the
  handoffs config skips the check.

## [0.1.0] - 2026-11-12

The first versioned release. Everything below it existed before versioning began: the backtesting
engine and API, the web app, sign-in with an admin and default permissions, the admin dashboard with
feature flags and an audit log, and the nightly price sync.

### Added

- Every merge to `main` is a release. It is tagged `v<major>.<minor>.<build>` and reaches production
  without a manual step: Railway applies pending database migrations before the new API takes
  traffic, and the web app is deployed only once the API reports the new release.
- The web app's footer shows the release it belongs to, as `v0.1.0 � <short commit>`.
- `GET /health` reports the commit the API is running, as `commit`.
- This changelog, with one section per release, checked on every pull request.

### Changed

- Production schema migrations are applied by the release itself. Running `supabase db push`
  against production is no longer part of a release; merge the migration with the code that needs
  it, and keep it additive.
- The web app is built and deployed by the release workflow instead of by Cloudflare Pages on each
  push, so it never goes live ahead of the API it calls. Pull requests no longer get preview
  deployments.
- Railway service settings live in the Railway dashboard, recorded in `docs/INFRASTRUCTURE.md`,
  instead of the config files Railway stops reading on 2026-12-01.
