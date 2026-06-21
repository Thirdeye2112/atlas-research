# Postgres Password Rotation Checklist

This is a manual checklist for the user to execute. **No step here has been run
by the agent.** Do not paste real secret values into chat, commits, or any
agent-readable file — fill them in directly in your shell / editor / the
Replit Secrets panel.

## 0. Prerequisites

- [ ] Confirm no running grind/backtest/training job is using the current
      `postgres` connection. Rotating the password will kill any open DB
      connections immediately. Check for:
      - Background PowerShell windows running `run_nightly.py`,
        `run_conditional.py`, `backtest_candlestick_outcomes.py`, or similar.
      - The Atlas Alpha API server process (`node ... dist/index.mjs`), if it
        holds a long-lived pool connection.
- [ ] Pick the new password. Recommended: a long random string with no shell
      special characters that need escaping in a PowerShell single-quoted
      string (avoid backtick, `$`, and double-quote; `?` and other
      URL-reserved characters are fine but will need percent-encoding in
      connection strings — simplest is to avoid them too).

## 1. Rotate the password in Postgres

Both `atlas_research` and `atlas_alpha` databases use the same shared local
`postgres` role, so this is a single rotation that affects both:

```sql
ALTER USER postgres WITH PASSWORD '<NEW_PASSWORD>';
```

Run this yourself via `psql` (or any client) connected as a superuser. The
agent will not run this command.

## 2. Update every `.env` file that references the old password

These are the only files known to hold the live credential on disk:

- [ ] `C:\Atlas\atlas-research\.env` — `DATABASE_URL=postgresql://postgres:<NEW_PASSWORD>@localhost:5432/atlas_research`
- [ ] `C:\Atlas\atlas-research-oos-diagnosis\.env` — same `DATABASE_URL` key, same DB
- [ ] `C:\Atlas\atlas-alpha\artifacts\api-server\.env` — update **both**:
      - `DATABASE_URL=postgresql://postgres:<NEW_PASSWORD>@localhost:5432/atlas_alpha`
      - `DATABASE_URL_RESEARCH=postgresql://postgres:<NEW_PASSWORD>@localhost:5432/atlas_research`
- [ ] If any other local worktree has its own `.env` copy (e.g. a worktree you
      created for parallel work), update it too — `git worktree list` in each
      repo will show you what exists.
- [ ] **Replit Secrets panel** (atlas-alpha deployment) — update the
      `DATABASE_URL` / `DATABASE_URL_RESEARCH` secret values there. This is a
      separate system from the local `.env` files; the agent has no access to
      it and cannot do this step.

If any connection string needs the password URL-encoded (special characters
in the password), re-encode it there — don't reuse a raw value that contains
unescaped reserved characters (`@`, `:`, `/`, `?`, `#`, etc.).

## 3. Restart anything holding an old connection

- [ ] Restart the Atlas Alpha API server process so it picks up the new
      `.env` values (it does not hot-reload env vars).
- [ ] Any long-running Python script/grind will need to be restarted after
      its `.env` is updated — it already has the old password loaded in
      memory and will start failing auth on its next query/reconnect.

## 4. Verify

- [ ] From `atlas-research`: run a trivial query (e.g.
      `scripts/check_alpha_db.py` or any script using `get_engine()`) and
      confirm it connects without a password-auth error.
- [ ] From `atlas-alpha`: hit `GET /api/healthz` and one DB-backed route
      (e.g. `/api/stock/:ticker`) and confirm it responds normally.

## 5. About git history

This checklist and the preceding refactor (branch `security/env-refactor`)
removed the hardcoded password from the **current tracked working tree** of
both repos. The old password **still exists in git history** in prior
commits (e.g. the original versions of the 8 refactored scripts, the two
`SKILL.md` files, and the removed log/asset files).

- [ ] Once you've completed steps 1–4 above, the old password in history
      becomes a dead credential — it no longer grants access to anything.
- [ ] Scrubbing it out of history (e.g. via `git filter-repo` or BFG) is
      **optional cleanup**, not a security requirement at that point, and is
      a separate, more invasive task (rewrites commit hashes, requires
      force-push, affects anyone else with a clone). Treat it as a future
      task if you want a fully clean history, not something to do as part of
      this rotation.
