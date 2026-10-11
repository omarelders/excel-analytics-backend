# Deployment notes

Operational facts that are not visible from the code or the deploy output. Read
this before the first deploy of the security-remediation branch.

## Required config var: `TRUSTED_PROXY_COUNT=1`

Set it **before** the web dyno boots:

```bash
heroku config:set TRUSTED_PROXY_COUNT=1
```

Heroku routes through one proxy, and the app refuses to start in production with
the hop count undeclared (`main.py` raises at import time, naming the variable).
Without the var the web dyno crash-loops with the app fully down.

**The release phase will not tell you.** The `release:` phase runs
`python run_migrations.py`, which never imports `main`, so the startup guard never
runs there: a release without the var exits **0** and Heroku marks the release
live. The only symptom is the crash-looping web dyno. After every deploy, check
the dyno:

```bash
heroku ps
heroku logs --dyno=web --tail
```

## The release phase is not a gate

`run_migrations.py` catches a failed migration, falls back to
`Base.metadata.create_all()`, and ignores its own return value, so the `release:`
phase exits **0** even when every migration failed. A green release says nothing
about whether the schema is right. Treat the web dyno's state as the deploy
signal, and confirm the schema yourself:

```bash
heroku run python run_migrations.py current
```

## Revision 002 logs every user out once

On the first deploy, revision `002_user_roles_and_auth` re-hashes session tokens
and deletes every pre-existing session row. This is deliberate and happens
exactly once: users log in again (passwords are untouched), and a lost admin is
recovered with:

```bash
python scripts/promote_admin.py <username>
```

## Verify migrations against Postgres before deploying

The migrations are exercised against SQLite by the test suite, so the Postgres
paths are unproven until they run. Run them against a staging Postgres database
first, before they run on the live one.

## Known limitation: Vercel preview deployments are refused by CORS

The frontend repo's `src/config/apiBaseUrl.js` treats any `*.vercel.app` host as
same-origin, so a preview deployment sends `Origin: https://<ref>.vercel.app`,
which the production CORS allow-list refuses. This is pre-existing and out of
scope for this branch.

To allow one preview deployment:

```bash
heroku config:set CORS_ORIGINS=https://<ref>.vercel.app
```

`*.vercel.app` is deliberately **not** allowlisted in production: a wildcard
subdomain in a credentialed CORS policy would let any Vercel deployment make
cross-origin requests as a logged-in user.
