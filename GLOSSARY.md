# TirelessInvest

A personal tool for backtesting and, later, running investment strategies. This glossary fixes the
words the project uses for itself; how anything is built belongs in the other docs.

## Language

### Releasing

**Version**:
The single `vX.Y.Z` number that names the whole product (API, web app and database schema
together) at one point on `main`.
_Avoid_: API version, web version, build number

**Release**:
A merge to `main`. Every release mints the next version and goes to production.
_Avoid_: cut, drop, deploy (a deploy is one step of a release)

**Breaking change**:
A change in what a user sees or gets back, such as a backtest computed differently or a feature
removed. It raises the major version. A change to the API or the schema alone is not one, because
they always ship together with the web app.
_Avoid_: API break, schema break
