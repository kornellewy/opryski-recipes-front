# Final Git + Playwright Verification Handoff — Opryski Recipes

Updated: 2026-09-09

This is the canonical verification record for the Anvil frontend. It reports
what was verified in the current checkout and keeps hosted blockers explicit.

## Source

Repository: `https://github.com/kornellewy/opryski-recipes-front.git`

Current checkout: `master`, clean after Anvil auto-sync, one local commit ahead
of `origin/master == bb8c74b`. That local commit adds only this handoff and the
two credential-safe Playwright runners; no application source was changed.
It has not been pushed from this environment.

The authoritative app source is `anvil.yaml`, `client_code/`, `server_code/`,
and `theme/`. The legacy package identifier `M3_App_1` is retained in the
manifest; the product display name is `Opryski Recipes`.

## Verified locally

- `python tests/test_server_code_contract.py`: **10 passed**.
- `anvil --json validate .`: **18 files valid**.
- Python compilation for gateway, state, helpers, and Forms: **PASS**.
- `git diff --check`: **PASS**.
- Server callables: **30/30 covered** by the contract harness.
- M3 source paths: **27 TextBox + 3 TextArea** under
  `m3._Components.TextInput`; stale direct paths: **0**.
- Client `typing` imports and `Any` annotations: **none**.
- Static component/click-handler/recipe/inventory/worker checks: **PASS**.

The local contract suite covers OAuth2 login fields, `/auth/me` rollback,
bounded read retries, mutation idempotency, no retry for login/mutations,
weather snapshot routing, export validation, HTTP error mapping, and all
callable registrations.

## Public hosted checks

Target: `https://jaunty-infamous-seal.anvil.app/`

- Application GET: **HTTP 200**.
- Page title: **Opryski Recipes**.
- Published bundle: corrected M3 component paths present; stale direct paths and
  the old `typing` error are absent.
- `/_/manifest.json`: **HTTP 200**, but currently reports `M3 App 1` for both
  `name` and `short_name`.

The manifest naming issue cannot be fixed by changing `package_name`: that is
the required internal identifier. The app owner must change the hosted Anvil
display/PWA name in the authorized IDE and publish it.

## Authenticated release blockers

The hosted runtime previously reported:

~~~text
anvil.secrets.SecretError: No such secret 'MVP_BASE_URL'
~~~

Therefore these remain **NOT VERIFIED** here:

- hosted `MVP_BASE_URL` and MVP CORS;
- real Server Module/Uplink request;
- owner and worker login plus `/auth/me`;
- recipe, inventory, weather-gated task, and cancellation flows;
- hosted 401/403/404/409 behavior.

The frontend origin must be allowed by MVP CORS, but it must not be used as
`MVP_BASE_URL`. Configure the secret to the separate external FastAPI MVP HTTPS
URL. Never commit or print secrets, JWTs, passwords, or Uplink keys.

## Playwright runners

The credential-safe runners are:

- `tests/playwright_manual_auth_qa.js`
- `tests/playwright_ephemeral_owner_qa.js`

They read credentials only from local environment variables, avoid printing
credential values, write status-only screenshots, and check desktop (1280x900)
and mobile (390x844) viewports. They require a local
Playwright installation supplied through `NODE_PATH`; this checkout does not
contain Playwright or Chromium, so they were not executed in this environment.

Example after configuring the authorized Anvil app:

~~~bash
export OPRYSKI_APP_URL='https://jaunty-infamous-seal.anvil.app/'
export OPRYSKI_OWNER_EMAIL='[set locally]'
export OPRYSKI_OWNER_PASSWORD='[set locally]'
export OPRYSKI_WORKER_EMAIL='[set locally]'
export OPRYSKI_WORKER_PASSWORD='[set locally]'
NODE_PATH=/path/to/playwright/node_modules node tests/playwright_manual_auth_qa.js
~~~

Use disposable accounts only. Production acceptance must remain blocked until
the hosted secret/CORS configuration, manifest name, and authenticated
owner/worker workflows pass at desktop and mobile widths.

## Release decision

~~~text
Source and local implementation: PASS
Anvil validation: PASS — 18 files valid
Public HTTP/bundle smoke: PASS
Manifest product name: BLOCKED — still M3 App 1
MVP_BASE_URL/CORS: BLOCKED — hosted secret not verified
Authenticated owner/worker QA: NOT RUN
Production acceptance: BLOCKED
~~~
