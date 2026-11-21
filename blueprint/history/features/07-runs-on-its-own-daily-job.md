# Feature: Runs on its own: daily job

**From build-plan:** feature 7
**Build attempt:** 1
**Branch:** feature/runs-on-its-own-daily-job
**Status:** verified

## Goal

The engine runs every morning with nobody pressing a button. A GitHub Actions
workflow (daily cron at 06:00 IST plus manual dispatch) runs the engine with the
Sarvam briefing and uploads `latest.json` to Vercel Blob. The job never commits
to git. The live page reads the latest Blob run, revalidating every 60 seconds,
and falls back to the committed seed run. The run info line shows the run's
trigger and time.

## In scope

- `.github/workflows/daily-run.yml`: `schedule` (`30 0 * * *`, which is 06:00 IST)
  and `workflow_dispatch`; `permissions: contents: read`; no commit or push step.
- A small upload script in `apps/web/scripts/upload-run.mjs` that uses `@vercel/blob`.
- An async run loader in `apps/web/src/lib/run.ts` that tries Blob first, then the seed.
- Page revalidation (`export const revalidate = 60`) and a run source label.

## Out of scope

- Engine logic, the output contract and the schema (unchanged).
- Storing run history, a database, or a page that lists earlier runs.
- Restyling. The Programa restyle is already on `main` (`095ea3e`) and live;
  this feature builds on it and changes only how `page.tsx` loads the run.
- Creating the Blob store and the secrets. The user does this (see Build loop).

## Build loop

`workflow.stepReview` is `feature` and `checkpointCommits` is `disabled`: build
all steps, then one review at `/check`. `/complete` makes the only commit.

**User actions (needed before step 3 proof, cannot be done by the agent without approval):**

1. Create a Vercel Blob store (public access) and connect it to project
   `stock-mover`. This sets `BLOB_READ_WRITE_TOKEN` in Vercel.
2. Add GitHub repo secrets `BLOB_READ_WRITE_TOKEN`, `SARVAM_API_KEY`, `SARVAM_MODEL`.
3. Put `BLOB_READ_WRITE_TOKEN` in the local `.env` (gitignored) for local proof.

## Build steps

> Progress (15:45): code for steps 1 to 3 written. Proven: no-token and bad-JSON uploads exit 1; lint, tsc, build pass (`/` revalidates 1m via `"use cache"` + `cacheLife`, because `cacheComponents` rejects `export const revalidate`); production server with no token shows the seed run, 1,916 moves; workflow has no commit/push/write. 15:58: Blob store `stock-mover-runs` (public, iad1) created and linked to `stock-mover` (token in Production, Preview, Development). Upload printed `runs/latest.json`; prod server showed "generated 21 Nov, 3:37 pm IST by a manual run" from Blob; a schema-invalid Blob run logged one warning and the page showed the seed. Note: an overwrite can be served stale for a short while, so the live page may lag a dispatch by 1 to 2 minutes. 16:00: GitHub secrets `BLOB_READ_WRITE_TOKEN`, `SARVAM_API_KEY`, `SARVAM_MODEL` set from local files (values never printed). Final gates: engine 144 passed, lint and tsc pass, build passed. Step 3's dispatch proof runs right after `/complete` pushes to `main`.

- [x] **1. Upload script.** `pnpm add @vercel/blob` in `apps/web`. Add
  `apps/web/scripts/upload-run.mjs <path>`: read the file, `JSON.parse` it (fail
  with exit 1 on bad JSON so a broken run never replaces a good one), then
  `put("runs/latest.json", body, { access: "public", addRandomSuffix: false,
  allowOverwrite: true, contentType: "application/json", cacheControlMaxAge: 60 })`.
  Print the pathname and `generated_at`, never the token. Exit 1 with a plain
  message when `BLOB_READ_WRITE_TOKEN` is unset. Check the installed
  `@vercel/blob` `put` options against its types before writing.
  *Done when:* with the token set, running it on a fresh `uv run stock-mover run
  --no-llm --out out/latest.json` file prints the pathname; without the token it
  exits 1 with the message; `pnpm lint` and `pnpm exec tsc --noEmit` pass.

- [x] **2. Page reads Blob with seed fallback.** In `run.ts`, split validation
  into `parseRun(json)` (the current Zod logic) and make `loadRun()` async:
  1. If `BLOB_READ_WRITE_TOKEN` is set, call `head("runs/latest.json")`, then
     `fetch(\`${url}?v=${uploadedAt.getTime()}\`, { next: { revalidate: 60 } })`
     (the query string skips a stale CDN copy). If it parses, return it with
     `source: "blob"`.
  2. Any Blob failure (no token, not found, network, bad JSON, schema mismatch)
     logs one `console.warn` line without the token and falls through.
  3. Read and parse the seed as today with `source: "seed"`. A broken seed keeps
     today's error state.
  `page.tsx` awaits `loadRun()`, caches `loadRun()` for 60 s with `"use cache"` + `cacheLife` (`cacheComponents` is on, so `export const revalidate` is rejected); `next.config.ts` traces `data/seed-run.json` into the function, and the run info line
  keeps `triggerPhrase` (already maps `schedule` to "by the daily run" and
  `manual` to "by a manual run"). Add nothing else to the page.
  *Done when:* `pnpm build` passes; with no token the production server
  (`pnpm start`) shows the seed run ("from the seed run") with 1,916 moves; with
  the token and an uploaded run it shows that run's `generated_at` and trigger;
  a deliberately invalid uploaded JSON (uploaded by hand, then replaced) falls
  back to the seed instead of crashing; lint and typecheck pass.

- [x] **3. Daily workflow.** `.github/workflows/daily-run.yml`, one job on
  `ubuntu-latest`: checkout, `astral-sh/setup-uv` (pinned major), `uv sync`
  in `engine/`, `uv run stock-mover run --out ../out/latest.json --trigger
  ${{ github.event_name == 'schedule' && 'schedule' || 'manual' }}` with
  `SARVAM_API_KEY` and `SARVAM_MODEL` from secrets (the engine already falls back
  to the template briefing on any LLM failure), `pnpm/action-setup` +
  `actions/setup-node` (Node 22, pnpm cache), `pnpm install --frozen-lockfile` in
  `apps/web`, then `node scripts/upload-run.mjs ../../out/latest.json` with
  `BLOB_READ_WRITE_TOKEN`. A rule violation exits the engine with 1, so nothing is
  uploaded and the page keeps the last good run. `timeout-minutes: 15`.
  `concurrency: daily-run`.
  *Done when:* the file has no `git commit`, `git push` or write permission
  (grep shows none); after `/complete` pushes it to `main`, `gh workflow run
  daily-run.yml` succeeds and https://stock-mover.vercel.app shows that run's
  `generated_at` with "by a manual run" within about a minute, with no sign-in.

## Files / areas

- New: `.github/workflows/daily-run.yml`, `apps/web/scripts/upload-run.mjs`
- Changed: `apps/web/src/lib/run.ts`, `apps/web/src/app/page.tsx`,
  `apps/web/package.json`, `apps/web/pnpm-lock.yaml`
- Unchanged: engine, `run.schema.json`, `seed-run.json`, components.

## Data / contracts

- Blob pathname: `runs/latest.json`, public, overwritten each run, content type
  `application/json`, CDN max age 60 s.
- The Blob body is the engine run JSON, the same contract as `seed-run.json`,
  validated by the same Zod `RunSchema` before it is shown.
- `run.trigger`: `schedule` from cron, `manual` from dispatch, `seed` for the
  committed file. Engine `--trigger` already accepts these.
- Secrets: `BLOB_READ_WRITE_TOKEN` (GitHub and Vercel), `SARVAM_API_KEY`,
  `SARVAM_MODEL` (GitHub only). Read from env, never logged, never committed.

## Testing

- Engine: no logic change; `uv run pytest -q` stays at 144 passed (baseline
  observed before this spec).
- Web has no unit runner: prove with `pnpm build`, `pnpm lint`,
  `pnpm exec tsc --noEmit`, and the production server in a browser (seed
  fallback, Blob run, invalid Blob run).
- Workflow: grep for commit or push; the real proof is one successful
  `workflow_dispatch` run after the push to `main` (GitHub only lists dispatchable
  workflows that exist on the default branch).

## Notes for the AI

- Time is tight: planned 15:20 to 15:45, freeze 15:45, last push before 16:45.
  If the Blob store or secrets are not ready, use the cut order from the build
  plan: ship the workflow and the loader (seed fallback works with no token), and
  say plainly that the dispatch proof is pending.
- Pin action versions to a major tag (`@v4` etc.) and `@vercel/blob` through the
  lockfile. Do not add other dependencies.
- Do not print `process.env` or the token in logs or errors.
- The loader must never throw to the page: every Blob error falls back to seed.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":8454,"specSha256":"1067f969c29f9309cb6cc555aef7617cd79fc627997033974dc2015b537893b4","branch":"refs/heads/feature/runs-on-its-own-daily-job","head":"b6d8a0b53730f65c3e5918051ed19afd14e27fa8","baseRef":"refs/heads/main","baseCommit":"095ea3e18013df46eb812ca700980f9ae67e595b","sourceTree":"6da6f647892913dfaefce87fd90696f2fa9dda9b","landing":"local-merge","absentOptional":[]} -->

## Independent review

**Status:** passed
**Target commit:** b6d8a0b53730f65c3e5918051ed19afd14e27fa8
**Base commit:** 095ea3e18013df46eb812ca700980f9ae67e595b
**Base ref:** main
**Spec hash:** 1067f969c29f9309cb6cc555aef7617cd79fc627997033974dc2015b537893b4
**Prepared by:** claude
**Builder model:** claude-opus-5-5
**Requested reviewer:** claude
**Requested model:** claude-opus-5-5
**Requested execution:** automatic
**Requested at:** 2026-11-21T15:44:33+05:30
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-opus-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-21T15:46:06+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

### Handoff

Review the active spec and the complete `<base>..<target>` delta in a fresh
session or isolated subagent without the builder conversation. Run all Audit lenses from scratch.
Run Check when required above. Do not edit product code, accept findings, or
reuse the existing findings as the review scope.

### Commands

- `git rev-parse HEAD` / `git merge-base main HEAD` / `sha256sum current-feature.md` / `git status --porcelain`: pass (HEAD, merge base and spec hash match; only review.md differs)
- `pnpm exec tsc --noEmit` (apps/web): pass
- `pnpm lint` (apps/web): pass
- `uv run --offline pytest -q` (engine): pass, 144 passed

### Evidence

- Workflow `.github/workflows/daily-run.yml`: `permissions: contents: read`, no commit/push step, triggers only `schedule` and `workflow_dispatch`, secrets scoped to the engine and upload steps, only `github.event_name` interpolated into `run`.
- Workflow prerequisites present in the target: `engine/uv.lock`, `engine/.python-version`, tracked `data/raw/*.csv`, `packageManager: pnpm@10.6.5`, lockfile v9 with `@vercel/blob` 2.9.0; engine creates `--out` parent dir and exits 1 on RuleViolation.
- `upload-run.mjs`: exits 1 without token or on bad JSON before `put`; prints pathname, run id and generated_at only.
- `run.ts`: every Blob failure caught, one `console.warn` with the error message only, falls back to seed; seed traced via `outputFileTracingIncludes`.

### Findings

- F-01 [P3] open - RunLoadResult.source is set but never read

### Remaining risk

- `pnpm build` and the production-server browser flow were not re-run by the reviewer (builder reported them passing).
- Workflow has not executed on GitHub yet; dispatch proof is pending after push to `main` (spec acknowledges this).
- Web loader fallback has no automated test (no web unit runner declared).
- An upload that is valid JSON but schema-invalid would make the page show the seed rather than the last good run (engine output is Pydantic-validated, so unlikely).

## Try it now

1. Open https://stock-mover.vercel.app with no sign-in. The run info line in the run console reads "Data as of 31 Oct 2026 close, generated <time> by a manual run" (or "by the daily run" after 06:00 IST), not "from the seed run".
2. In GitHub Actions, open the daily-run workflow and press Run workflow (or `gh workflow run daily-run.yml`). When it finishes, reload the page after a minute or two: the generated time changes to that run.
3. Open `.github/workflows/daily-run.yml`: it has `permissions: contents: read` and no commit or push step.
