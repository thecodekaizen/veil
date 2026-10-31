# Draft: README "Provenance" section (not yet in README)

## Provenance

Commits before `8728e71` (Oct 25–26, 2026) belong to the earlier THREAD prototype and are not
part of this submission. The building period is Oct 27 – Nov 4, 2026. Commits from Oct 27 up to
`610a395` (Oct 28) are THREAD / SHOWME experiments; all Veil work dates from `610a395`
(Oct 28, 2026, "Build VEIL real Meta privacy smoke pipeline and verified export") onward.
The git history has not been rewritten.

Pre-Oct-27 files that still exist in HEAD (from the THREAD prototype): `backend/thread_engine/*`,
`apps/web/*` (Next.js), `datasets/*`, `design/*`, `docs/{ARCHITECTURE,DATA_MODEL,DEMO,DISCOVERY_ENGINE,EVALS,PLAN,PRODUCT}.md`.
None of them is imported or used by the Veil package (`veil/src`, `veil/web`, `veil/tests`, `veil/scripts`).
Repo-level `README.md`, `AGENTS.md` and `.gitignore` also began in that period but have since been rewritten for Veil.
