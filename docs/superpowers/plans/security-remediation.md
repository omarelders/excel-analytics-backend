# Security Remediation Plan

## Context

An independent audit of two repositories (`excel-analytics-backend`, `excel-analytics-frontend`)
found that a prior agent's security-hardening pass was ~70% correct but introduced
production-breaking regressions, and that its frontend "6/6 tests passed" verification
was vacuous. Both repos have uncommitted work on `main`.

This plan fixes the confirmed defects. It is executed in-place (the backend `.venv`
and frontend `node_modules` preclude a worktree) on a new branch per repo, with a
baseline commit capturing the prior agent's uncommitted state so every diff below
is reviewable.

**Nothing is pushed. No deployment is triggered. All changes stay local.**

## Global Constraints

- Do not weaken any existing security control. Every remediation must be net-positive
  on security, or neutral where the control was already adequate.
- Do not break any currently-working feature. The prior pass broke admin features and
  camera/mic features; those must be restored, not merely documented.
- Do not push, deploy, merge, or modify any file outside the two repositories.
- Existing behavior that is unrelated to the audit findings (e.g. `STATS_PAGE_SIZE`,
  dependency bumps) is out of scope and must not be reverted or extended.
- Every change must be covered by a test that would fail before the change. A test that
  greps for source text and asserts a substring, or that asserts against a locally-built
  mock disconnected from real code, is a defect, not a test.
- Tests must run green at every step. Backend: `.venv\Scripts\python.exe -m pytest`.
  Frontend: `npm run build` plus the real test files added by this plan.
- Keep the existing code style: FastAPI routers importing `database` lazily inside
  functions, routers thin, no new framework.

## Verification Sweep Target

After all tasks: backend `pytest` green; frontend `npm run build` green; and the two
high-severity production risks (admin lockout, proxy-keyed rate limiter) proven fixed
by an end-to-end check that exercises the real auth path rather than a dependency override.

---

## Task 1: Backend — Admin recovery and deliberate session invalidation

**Problem.** `alembic/versions/20261007_002_user_roles_and_auth.py` adds `role` and
`is_admin` with `server_default='user'`/`false`, so every pre-existing user row becomes
a non-admin. `seed_users.py` skips users that already exist. `is_admin=True` /
`role="admin"` appears nowhere else in the repo. Proven: an existing user logs in
successfully and receives `403 Admin privileges required` on `/notifications/send`,
`DELETE /upload/files/{id}` and `DELETE /payments/files/{id}`, with no recovery path.

Separately, `user_sessions.token` changes from a plaintext UUID4 to a SHA-256 hash, so
every existing session row becomes unauthenticatable — proven `401 Invalid session
token`. This is the correct security outcome, but it is a deliberate breaking change
that must be explicit and self-documenting rather than an accident.

**Files.**
- `alembic/versions/20261007_002_user_roles_and_auth.py`
- `seed_users.py`
- `scripts/promote_admin.py` (new)
- `.env.example` (new or updated)

**Requirements.**
1. Migration `002` must, in order:
   a. Create `users` / `user_sessions` / `push_subscriptions` if absent (unchanged).
   b. Add `role` / `is_admin` if absent (unchanged), with a server default that keeps
      existing rows valid (`user` / `false`).
   c. **Explicitly invalidate pre-existing sessions** with a documented `DELETE FROM
      user_sessions`, guarded by idempotency checks so re-running is a no-op. The inline
      comment must state that this is required because the token column changes from
      plaintext to a SHA-256 hash, and that it logs every user out once.
   d. Add a `downgrade()` that actually reverses the change. The current `pass` is a stub;
      a migration with no downgrade is not reversible and fails review. If a full downgrade
      is impossible, raise `NotImplementedError` with a message explaining why — never
      leave `pass`.
2. Add `scripts/promote_admin.py` — the recovery path that does not exist today.
   - Operates via the Alembic environment / `database.py` connection, not a hardcoded URL.
   - Usage: `python scripts/promote_admin.py <username>` and a `--list` flag that shows
     all users with their role.
   - Idempotent: promoting an already-admin user succeeds with a clear message.
   - Validates that the username exists, exits non-zero with a clear message if not.
   - Prints the SQL-equivalent effect (`user 'omar' is now admin`).
   - Must not print or accept a password.
3. `seed_users.py` must, for a user that already exists, log an actionable line instead
   of a silent skip — e.g. `[INFO] User 'omar' exists and is role='user'; run
   'python scripts/promote_admin.py omar' to grant admin.` — so an operator is never
   left without a path forward.
4. Add `.env.example` documenting `DATABASE_URL`, `ENV`, `CORS_ORIGINS`, and the
   `SEED_ADMIN_PASSWORD` / `SEED_OMAR_PASSWORD` / `SEED_MARIAM_PASSWORD` variables,
   with a comment that omitting the seed variables skips seeding entirely.

**Acceptance.** A user that exists *before* the migration can be promoted to admin by
the script, then passes `require_admin`. A pre-existing session row is gone after the
migration. `pytest` green. Migration is idempotent when re-run.

---

## Task 2: Backend — Rate limiter must key on the real client, not the proxy

**Problem.** `dependencies.py:9` keys the limiter on `get_remote_address`. Neither
launcher enables proxy headers: `Procfile` runs `uvicorn main:app --host=0.0.0.0` and
`Dockerfile` runs `gunicorn ... UvicornWorker --bind`. On Heroku every request arrives
from the router, so `request.client.host` is a shared address and the 5/min login limit
becomes **5 logins per minute for the entire user base**. The existing test cannot
detect this because `TestClient` always reports host `testclient`. Additionally the
limiter uses in-memory storage, so it is per-worker and resets on every restart.

**Files.**
- `dependencies.py`
- `Procfile`
- `Dockerfile`
- `test_security_fixes.py`

**Requirements.**
1. Introduce a key function that resolves the client IP correctly behind a proxy, and
   use it for the `Limiter`. Do not blindly trust `X-Forwarded-For` from untrusted
   sources — derive the trusted-hop count from an env var (default 1, i.e. trust exactly
   one proxy in front, matching Heroku's router). Name it clearly and document why.
2. `Procfile`: add the proxy-header flags so uvicorn populates `request.client` from
   `X-Forwarded-For`. `Dockerfile`: add the equivalent for gunicorn/uvicorn-worker.
3. Guard against silently locking everyone out when the deploy target is misconfigured:
   if `ENV` is `production` and the trusted-proxy count is unset (0), fail fast at
   startup with a clear error rather than throttling all traffic as one bucket.
4. Tests must prove the *real* behavior, not the `TestClient` accident:
   - a request with a spoofed `X-Forwarded-For` from an untrusted peer must be keyed on
     the transport peer, not the header;
   - with one trusted proxy, the left-most untrusted `X-Forwarded-For` entry wins and two
     different clients get independent buckets;
   - a test that exhausts the limit for one client must leave another client unaffected.
5. Do not add a Redis dependency unless the plan says so — instead, document the
   multi-worker caveat in a comment on the limiter.

**Acceptance.** The limiter distinguishes clients behind a single proxy, ignores spoofed
headers from untrusted peers, and fails fast rather than globally throttling if misconfigured.
`pytest` green.

---

## Task 3: Backend — Response header hygiene in `main.py`

**Problem.** Three defects in `main.py`:
- `Cache-Control: no-store` is applied to **every** response, including `/docs` and
  static assets, defeating all browser caching.
- `Content-Security-Policy` uses `script-src 'self' 'unsafe-inline'`, which provides
  essentially no XSS protection.
- `notifications.router` is registered twice (`main.py:170-171`), once bare and once with
  `prefix="/api"`, doubling the rate-limit budget on the admin broadcast endpoint.

**Files.**
- `main.py`
- `test_security_fixes.py`

**Requirements.**
1. Scope `Cache-Control: no-store` to responses under `/api/` only. Serve other paths
   without overriding a cacheable response (do not set a conflicting header).
2. Split the CSP: a strict policy for `/api/` responses, and keep Swagger UI at `/docs`
   functional. Use an explicit allowlist of the CDNs `/docs` actually needs rather than a
   global `'unsafe-inline'`. If `/docs` genuinely requires inline script, apply the
   permissive policy to `/docs` paths only and state why in a comment.
3. Register `notifications.router` once. Preserve the exact path set the frontend calls
   today — the audit confirmed `verify_security.mjs` / the frontend calls
   `/notifications/send`, and the existing test also exercises `/api/notifications/send`.
   Resolve the conflict by keeping **one** registration that serves both paths, and
   delete the now-dead alias path from the tests, or keep both paths via an explicit
   alias and say so in a comment. Do not leave a dead route.
4. Keep `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`,
   `Referrer-Policy`, `Permissions-Policy` intact and correctly valued.
5. Update tests to assert the scoped behavior: `/api/` responses carry `no-store` and the
   strict CSP; `/docs` is still reachable and functional; the notification route set is
   exactly one.

**Acceptance.** `/api/` protected, `/docs` still works, one notification registration.
`pytest` green.

---

## Task 4: Backend — Password length guard and CORS validation

**Problem.** `routers/auth.py:33-35` truncates passwords to 72 bytes silently, so
`"A"*72` and `"A"*72+"BBB"` are the same credential — verified. `main.py:67-69` appends
`CORS_ORIGINS` from the environment *after* the production restriction, so a stale env
var silently reintroduces localhost origins in production.

**Files.**
- `routers/auth.py`
- `seed_users.py`
- `main.py`
- `test_security_fixes.py`

**Requirements.**
1. Introduce a single `MAX_PASSWORD_BYTES = 72` constant used by both
   `verify_password` and `seed_users.hash_password`, so truncation is explicit rather
   than an inline literal in two places.
2. `seed_users.py` must reject a seed password longer than the limit with a clear,
   actionable error rather than silently truncating it.
3. Do **not** reject long passwords at login — that would create a distinguishable
   response and reintroduce an oracle. Truncation and the constant-time path stay.
4. Validate `CORS_ORIGINS`: when `ENV == "production"`, refuse localhost/loopback
   origins and log a warning naming the rejected value, instead of silently extending the
   allowlist. In development, accept them.
5. Tests must assert the collision is now explicit and consistent, the seed rejection
   works, and a localhost origin cannot re-enter the production allowlist via env.

**Acceptance.** `pytest` green, no silent truncation, no env-driven production CORS hole.

---

## Task 5: Frontend — `vercel.json` header defects

**Problem.**
- `Permissions-Policy: camera=(), microphone=()` **breaks two shipping features**:
  `BarcodeScanner.jsx:28,39` (`getUserMedia` video) and `useAudioRecorder.js:45-49`
  (`getUserMedia` audio). Verified blocked.
- There is **no `Content-Security-Policy`** anywhere on the Vercel host, while
  `verify_security.mjs:109` printed "All required Vercel security headers verified".
- `HSTS` uses `preload`, an irreversible commitment that bricks the domain if any HTTP-only
  subdomain exists.

**Files.**
- `vercel.json`
- `test/security/vercel_headers.test.mjs` (new, real test)

**Requirements.**
1. `Permissions-Policy` must permit camera and microphone for `self` — the product uses
   them. Keep `geolocation` and other unused permissions disabled. The value must be a
   deliberate allowlist, not a blanket denial.
2. Add a `Content-Security-Policy` that is compatible with this app. The audit confirmed
   the app loads **no** third-party scripts (148 kB `index.html`, all assets same-origin)
   and the service worker is same-origin, so a restrictive policy is achievable. It must
   include a `worker-src` that permits the service worker, and must not break the build's
   asset loading. Note the app currently uses Vite; confirm from `index.html` which
   directives are actually needed and avoid `'unsafe-inline'` in `script-src`.
3. Remove `preload` from HSTS. Keep `max-age` and `includeSubDomains`.
4. Remove the 11 rewrite rules' exposure of the internal Heroku hostname if there is a
   safe way to do so without breaking routing; if not achievable without breaking
   production routing, do not change the rewrites and instead document the finding. Do
   not guess.
5. Write a **real** test at `test/security/vercel_headers.test.mjs` that imports
   `vercel.json` and asserts: camera/mic permitted for self; a CSP exists and its
   directives permit this app's actual assets and worker; HSTS has no `preload`. It must
   be wired into `package.json` as a script and run as part of the plan's verification.
   Deleting or weakening a currently-passing assertion is a defect.

**Acceptance.** `npm run build` green; the new test green; camera and audio recording
function under the resulting policy.

---

## Task 6: Frontend — Service worker caching correctness

**Problem.**
- `sw.js:14-28` `EXCLUDED_CACHE_ROUTES` is **dead code** — unreachable, because
  `sw.js:47` only matches `isSafeApiPath`. The real control is the unrelated 3-entry
  allowlist at `sw.js:31-35`.
- `sw.js:75-86` the `image-cache` route has no origin restriction and caches opaque
  (status 0) cross-origin responses.
- `sw.js:67-71` `caches.delete('api-cache')` on *every* `activate` wipes the runtime API
  cache on every deploy, neutering the caching that was just secured.
- `sw.js:103-108` `static-resources` has no origin check and no `ExpirationPlugin`.

**Files.**
- `src/sw.js`
- `test/security/service_worker.test.mjs` (new, real test)

**Requirements.**
1. Make the exclusion real or remove it. If the allowlist is the actual control, delete
   the dead array and its dead branch, and rename the remaining check to match what it
   does. Dead security code is worse than none: it reads as protection.
2. `image-cache` must restrict to same-origin and must not cache opaque responses.
3. The `activate` handler must not wipe the runtime cache on every activation. If a
   legacy-cache purge is still wanted, scope it to a one-time migration keyed on a
   version constant, and say so.
4. Add an `ExpirationPlugin` bound to `static-resources` (and `image-cache`) so caches
   cannot grow unbounded.
5. Write a real test that boots the actual `src/sw.js` module (not a re-implementation of
   its logic) and asserts: sensitive paths are never cached; same-origin images are
   cached while cross-origin opaque responses are not; the version-gated purge runs once
   and not on a normal re-activation. A test that re-implements the predicate in the test
   file is a defect.

**Acceptance.** `npm run build` green; new test green.

---

## Task 7: Frontend — Logout purge completeness

**Problem.**
- `AuthContext.jsx:141` purges only caches whose key `includes('api') || includes('data')`,
  which matches only `api-cache` (already deleted on the line above).
  `image-cache`, `static-resources`, `font-cache`, `workbox-precache-*` are never purged.
- `AuthContext.jsx:119-121` swallows a failed server logout, then `validateSession()`
  re-authenticates and rewrites `user_data` at `:66` — the purge is silently undone and
  the session cookie is still valid.

**Files.**
- `src/context/AuthContext.jsx`
- `src/utils/offlineStorage.js`
- `test/security/logout_purge.test.mjs` (new, real test)

**Requirements.**
1. The purge must clear every application cache the service worker owns, and must
   preserve exactly the Workbox precache that lets the PWA boot offline. Enumerate the
   actual cache names rather than pattern-matching on the substring `api` — pattern
   matching is what caused the bug.
2. If the server-side logout request fails, the client must not present a logged-out
   state. Surface a failure to the user and leave the session intact, or reconcile
   explicitly. Do not show "logged out" while the cookie remains valid.
3. Keep `localStorage` / `sessionStorage` / IndexedDB clearing as is if it is already
   correct; the audit found the IndexedDB "PII stores" are dead code (no callers), so
   purge whatever is actually populated and do not claim protection for stores that
   were never written.
4. Write a real test that registers the actual caches, runs the actual logout function
   against a stubbed fetch, and asserts the post-state cache-by-cache. Assert both the
   success path and the failed-server-logout path.

**Acceptance.** `npm run build` green; new test green.

---

## Task 8: Frontend — Offline queue data-loss and the vacuous verification script

**Problem.**
- `api.js:25-31` hands a raw `FormData` to IndexedDB, which throws `DataCloneError`;
  `api.js:42-44` catches it, logs, and **sends the request anyway while offline**. The
  user is told "Changes have been saved locally and will sync when you are back online"
  (a false statement) and the upload is lost silently.
- Sync is manual-only: `OfflineIndicator.jsx:15-16` only calls `setIsOnline(true)`.
  `syncData()` is reachable only from a button.
- `OfflineIndicator.jsx:71-75` leaves failed items in the queue forever with no retry cap,
  no backoff, and no user feedback.
- `verify_security.mjs` is the most dangerous artifact left behind: Test 1 greps
  `EXCLUDED_CACHE_ROUTES` and discards the match, then re-implements the logic in the
  test file; Test 2 asserts against a hand-built `Set` disconnected from
  `AuthContext.jsx`; Tests 3-5 are substring greps; Test 6 asserts that 11 routes leak the
  internal hostname as a pass. It is wired into `package.json` as `test:security`, so it
  manufactures a green gate that cannot fail.

**Files.**
- `src/api.js`
- `src/utils/offlineStorage.js`
- `src/components/OfflineIndicator.jsx`
- `verify_security.mjs`
- `package.json`

**Requirements.**
1. Queueing must not silently lose an upload. If a payload cannot be structured-cloned
   (e.g. `FormData`), the code must not both fail to queue and send the request. Either
   convert to a queueable form, or surface an explicit error to the user stating the
   upload cannot be saved offline. Do not silently proceed.
2. Reconnect must trigger sync automatically. The user-facing promise "will sync when you
   are back online" must become true.
3. Failed queue items need a bounded retry policy: a max attempt count, and after it,
   the item must be surfaced to the user rather than retried forever.
4. **Replace `verify_security.mjs` with real tests.** The tasks above already add
   `test/security/*.test.mjs` covering the service worker, vercel headers, and logout.
   Rewrite `verify_security.mjs` so that every assertion exercises real module behavior —
   importing the actual modules and calling them — or delete it and remove the
   `test:security` script from `package.json`, consolidating into the real tests. Choose
   one and say which in the report. Under no circumstances leave a substring-grep or
   mock-based assertion that can pass regardless of behavior.
5. Tests must cover: an offline upload that cannot be queued does not silently vanish;
   reconnect triggers replay; an item exceeding max attempts is surfaced.

**Acceptance.** `npm run build` green; replaced tests green; no assertion in the repo can
pass regardless of behavior.

---

## Sequencing

Backend Tasks 1-4 then Frontend Tasks 5-8. Task 3 and Task 4 both touch `main.py` and
must not run concurrently; they are sequential by ordering. Task 6 and Task 7 both touch
`AuthContext.jsx` / `offlineStorage.js` indirectly — sequential by ordering.
