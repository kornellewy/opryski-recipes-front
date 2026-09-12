# Opryski Recipes — Canonical Verification Handoff

Updated: 2026-09-12

This record describes the current Anvil source package and the evidence
available from this checkout. Production acceptance remains blocked until the
external MVP connection and authenticated hosted workflows are exercised.

## Source and layout

Repository: `https://github.com/kornellewy/opryski-recipes-front.git`

The current Anvil package uses `anvil.yaml`, `client_code/`, `server_code/`,
and `theme/`. Its startup form is `Form1`; `client_code/App/` is a shared
client package containing state and display helpers, not an `App` Form. The
`client/app.py:App` setup prompt refers to a different package layout and must
not be applied by changing this app's `startup_form` to a nonexistent Form.

The source manifest contains:

~~~yaml
name: Opryski Recipes
metadata:
  title: Opryski Recipes
package_name: opryski_recipes
startup_form: Form1
~~~

`package_name` is the internal Anvil identifier. The product display title is
`Opryski Recipes`. The published PWA manifest currently derives its name as
`opryski_recipes`; changing that hosted setting requires the authorized Anvil
IDE.

## Local implementation

- Material 3 source paths: 27 `TextBox` and 3 `TextArea` under
  `m3._Components.TextInput`; stale direct paths: 0.
- Client code has no `typing` import or `Any` annotation.
- Owner navigation, recipe validation/copy/export, inventory balances/lots/
  receipt/movements/reservation details, and worker mobile tabs are present.
- Unsupported capabilities remain disabled and labelled `Planowane`.
- The gateway keeps JWTs in `anvil.server.session`, sends OAuth2 login fields,
  validates `/auth/me`, retries read-only requests, and gives mutations one
  fresh idempotency key. Login and the read-only weather snapshot do not get
  mutation keys.
- A missing `MVP_BASE_URL` secret now returns an explicit configuration result
  instead of raising an Anvil runtime error screen.

## Automated checks

Executed in this checkout:

~~~text
python tests/test_server_code_contract.py: PASS — 11 tests
Server callable registrations: PASS — 30/30
anvil --json validate .: PASS — 18 files valid
Python compilation: PASS
Client typing/Any scan: PASS
M3 stale/corrected path scan: PASS — 0 stale, 30 corrected
Component and click-handler checks: PASS
git diff --check: PASS
Credential scan: PASS — no real credentials
~~~

The added missing-secret regression test covers the hosted failure mode seen in
the earlier browser run. Playwright runner scripts are syntax-valid, but this
checkout does not include Playwright or Chromium, so authenticated browser
flows were not executed here.

## Public hosted smoke

Target: `https://jaunty-infamous-seal.anvil.app/`

Direct HTTP checks from this environment:

~~~text
Application GET: HTTP 200
HTML title: Opryski Recipes
Manifest GET: HTTP 200
Published bundle: corrected TextInput M3 path present; stale path absent
~~~

The current manifest response reports `name` and `short_name` as
`opryski_recipes`, not the requested human-readable `Opryski Recipes`. The
authorized owner must change the hosted display/PWA name and publish it.

## Hosted MVP and authentication status

`https://jaunty-infamous-seal.anvil.app` is the frontend origin. It belongs in
the external MVP CORS allowlist and must not be used as `MVP_BASE_URL`.

The Anvil Secret `MVP_BASE_URL` must contain the separate published HTTPS URL
of the FastAPI MVP. Its hosted value, hosted CORS, real Server Module/Uplink
requests, owner/worker login, recipe, inventory, weather gates, task
transitions, cancellation, and hosted 401/403/404/409 checks are not verified
from this environment. No credentials, JWTs, or keys were used.

The reported Anvil publish attempt was denied for app `GG6QEJZ4UB72TQJU`; the
owner must publish from an authorized Anvil account. Any previously exposed
Uplink keys must be revoked and rotated before Uplink use.

## Required owner actions

1. Open the intended app in the authorized Anvil IDE and confirm the imported
   source uses `Form1` as startup form.
2. Confirm the Material 3 dependency `m3` version `v1.2.6` resolves.
3. Publish the current source, including the missing-secret handling fix.
4. Set `MVP_BASE_URL` to the external FastAPI MVP URL and allow the Anvil
   origin through MVP CORS.
5. Change the hosted PWA/display name to `Opryski Recipes`.
6. Run disposable owner and worker browser flows at desktop and mobile widths,
   including recipe, inventory, weather-gated task transitions, cancellation,
   and visible 401/403/404/409 handling.
7. Save screenshots and console/network results without storing credentials.

## Release decision

~~~text
Source and local implementation: PASS
Gateway and callable contract: PASS — 11 tests, 30 callables
Anvil validation: PASS — 18 files valid
Public HTTP/title/bundle smoke: PASS
Hosted manifest human-readable name: BLOCKED — currently opryski_recipes
Hosted MVP_BASE_URL/CORS: BLOCKED — not verified
Authenticated hosted QA: NOT RUN
Production acceptance: BLOCKED
~~~
