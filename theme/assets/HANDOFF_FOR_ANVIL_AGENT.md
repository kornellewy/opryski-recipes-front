# Handoff for the Python Anvil frontend coding agent

This file is the implementation contract for the Anvil-side frontend. Read it
before writing forms or server calls. The local Python MVP is the source of
truth for auth, recipes, weather, task state, and audit records.

## 1. Product and architecture

`opryski-recipes` is a Polish orchard-spraying management app for sadownicy.

- **Local MVP (`mvp/`)**: FastAPI, SQLite, JWT/bcrypt auth, workers, recipes,
  tank-mix ordering, weather, karencja guard, spray state machine, audit
  snapshot, online SQLite backup.
- **Anvil app**: UI only. The complete source package is in `anvil_app/` and
  calls the MVP through its Anvil Server Module gateway. Do not duplicate auth,
  weather thresholds, recipe calculations, catalog data, or transition rules in
  Anvil.
- **Demo visual reference**: `demo/opryski-recipes-demo.html` — Luna-style
  single-file prototype with left owner rail and worker bottom tabs.
- **Canonical API docs**: `uplink/spec/endpoints.md`, `auth.md`,
  `recipes.md`, `weather.md`; live machine schema is `GET /openapi.json`.
- **Anvil import map**: `anvil_app/IMPORT_MAP.md`; package overview:
  `anvil_app/README.md`.
- **Not implemented in this MVP**: `OPEN_ISSUES.md`. Render those items as
  disabled/roadmap UI, not successful buttons.

The MVP uses UUID strings for recipe, kwatera, and task IDs. A fresh database
is required after the 0.2 schema change; there is no migration tool yet.

## 2. Local startup for the backend

From the repository root:

```bash
cd mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env # then set a real JWT_SECRET; load it in the shell
export JWT_SECRET='a-random-secret-at-least-32-characters-long'
export CORS_ORIGINS='http://127.0.0.1:7765,http://localhost:7765'
python -m uvicorn server:app --host 127.0.0.1 --port 7765
```

For a clean isolated verification, use:

```bash
bash uplink/scripts/run_all.sh
```

The script creates a temporary DB, temporary backup directory, per-run secret,
starts the MVP, waits for `/healthz`, runs every endpoint/response assertion,
and removes everything on exit. It does not write to the developer's real
`~/backups/opryski` directory.

## 3. Uplink usage in Anvil

Import `anvil_app/server/uplink_client.py` and `anvil_app/server/api.py` as
Anvil Server Modules. The callable gateway stores the JWT only in
`anvil.server.session`; never place the MVP secret or passwords in client UI.

```python
from anvil import server

me = server.call("mvp_login", email, password)
dashboard = server.call("mvp_dashboard")
```

Set the published MVP HTTPS URL in Anvil configuration. Configure the same
published Anvil origin in the MVP `CORS_ORIGINS` environment variable.

## 4. Owner desktop UI

Use a clean, low-density, Polish-language desktop/tablet layout matching the
demo:

Left vertical rail:

- Panel
- Mapy
- Opryski
- Receptury
- Pracownicy
- Katalog
- Pogoda
- Raporty
- Ustawienia

Top bar: farm name, live weather chip, notifications, owner avatar.
Use semantic status **with icon + text**, not colour alone:

- green = Bezpiecznie / można autoryzować
- yellow = Uwaga / nieoptymalne
- red = Zablokowane / nie wykonuj
- blue/grey = neutral/informational

Owner dashboard must call:

- `GET /auth/me`
- `GET /kwatery`
- `GET /spray-tasks`
- `GET /weather/current?lat=&lon=`

The active task card shows kwatery, recipe, worker, scheduled time, weather
status, and current task status. The `Autoryzuj` button is enabled only after
`worker_confirmed`; the server is the final authority and may return 409.

## 5. Worker mobile PWA

Use a responsive layout with a fixed bottom bar:

- Dziś
- Zadanie
- Mapa

Primary worker actions must be 56–64 CSS pixels high; never below 48 px. Show
large text and explicit status labels for rain/glove use.

Worker task screen:

1. O zabiegu — kwatera, reason, parcel number, scheduled time
2. Receptura — call `/recipes/{id}/compute`; display server `mixing_order` and
   totals; do not calculate doses in Anvil
3. PPE — show the recipe/product data available from the MVP; prewencja is a
   Phase 2 disabled/roadmap item until the endpoint exists
4. Gotowe — button sequence controlled by server response

A worker may only call the actions on their assigned task:

`dispatch -> worker-confirm -> owner-authorize -> execution-started -> execution-completed`

The worker app must handle 401/403/404/409 visibly:

- 401: session expired; show login
- 403/404: task is not assigned/visible
- 409: stale or illegal state; refresh task list and show server reason

## 6. Auth and worker setup

Public register creates an owner only:

```python
POST /auth/register
{"email":"owner@example.com","password":"...","full_name":"Marek Kowalski"}
```

Owners create workers:

```python
POST /workers
{"email":"worker@example.com","password":"...","full_name":"Janusz Wiśniewski"}
```

A worker is linked to exactly one owner farm. There is no public role selector.
The owner and assigned worker must be different accounts.

## 7. Recipe builder

Create recipe with:

```json
{
  "name": "Parch jabłoni — wiosna 2026 v3",
  "target": "parch jabłoni",
  "products": [
    {"catalog_product_id":"<catalog UUID>","name":"Delan 700 WG","formulation":"WG","dose_per_ha":0.5,"unit":"kg","dose_basis":"ha"},
    {"catalog_product_id":"<catalog UUID>","name":"Captan 80 WDG","formulation":"WDG","dose_per_ha":1.9,"unit":"kg","dose_basis":"ha"}
  ],
  "water_l_per_ha":600
}
```

The server validates positive doses and product count. `compute` returns total
doses and the canonical order:

`WSB/SG -> WP -> WG/WDG/DF -> SC/CS/FS/F -> EW -> SE -> OD/DC -> ME -> EC -> SL/SP -> adjuvant`

The MVP now stores catalog-linked recipe components and has internal draft-label
extraction infrastructure. It does not yet validate recipe rates against a
human-reviewed label use. Mark extracted data as advisory; never call machine
extraction legal approval.

## 8. Spray task and compliance fields

Task creation requires and server-locks:

- `przyczyna`
- `application_type` (`polowe` or `szklarnia`)
- assigned `worker_id`
- `executor_name` matching the worker's name
- `bbch_at_spray`
- `actual_dose_per_product` exactly matching the recipe
- `nr_dzialki_ewidencyjnej` copied from each kwatera
- `weather_snapshot`
- `t_source` and optional `client_timestamp`

The server rejects a task when a selected kwatera has active `karencja_until`.
It also rejects overlapping active tasks on the same kwatera.

Audit events include UTC server time, actor, state, `t_source`,
`server_delta_ms`, and compliance payload. Treat returned `audit` as read-only.
Never make the frontend the authority for PIORiN fields.

## 9. Exact state machine

```text
created -> dispatched -> worker_confirmed -> owner_approved
       -> execution_started -> execution_completed

created/dispatched/worker_confirmed/owner_approved/execution_started
       -> cancelled
```

Terminal states are `execution_completed` and `cancelled`. The server returns
409 for an illegal transition. Refresh after every transition; do not optimistically
invent a new state.

Cancellation body:

```json
{"reason_code":"weather_changed","partial_mix_disposed":false}
```

## 10. Weather

Call `/weather/current` from the MVP. It returns Open-Meteo data and a
suitability object. Display `delta_t_method: magnus_approx` as an approximate
badge.

Only a task snapshot with `suitability.status == "green"` passes owner
authorization. Never encourage spraying on yellow or red. Phase 2 adds rain,
validated wet-bulb delta-T, wind direction, and buffer zones.

## 11. Explicit MVP limits

Do not implement successful flows for these yet:

- PIORiN PDF/A-3 export
- inventory reserve/deduct/release
- prewencja/REI calculation
- SMS provider/GSM-7 fallback
- bee/public-road/water-buffer overlap checks
- recipe or kwatera update/delete
- stale confirmation/offline replay correction
- billing/multi-farm administration

Put them behind disabled controls with a `Planowane` label and link them to
`OPEN_ISSUES.md` in developer documentation.

## 12. Acceptance checklist for the Anvil build

- [x] Owner register/login works; role cannot be selected by the user.
- [x] Owner creates a worker and worker can log in.
- [x] Owner creates kwatera with parcel number, validated GeoJSON, read-only OSM link, and sees karencja lock.
- [x] Owner creates a catalog-linked draft recipe and UI uses server mixing order/total doses.
- [x] Owner creates and dispatches a task with all compliance fields.
- [x] Assigned worker confirms; another worker is rejected.
- [x] Owner cannot authorize before worker confirmation.
- [x] Yellow/red weather cannot be authorized.
- [x] Worker can start/complete only after owner authorization.
- [x] Owner can cancel a non-terminal task with reason and disposal flag.
- [x] 409 responses refresh state instead of showing success.
- [x] `bash uplink/scripts/run_all.sh` reports all steps green.

## 13. Complete Anvil source package

The requested Anvil implementation has been created under `anvil_app/`:

| File | Purpose |
|---|---|
| `server/api.py` | Server-callable gateway, JWT session, all MVP operations |
| `server/uplink_client.py` | HTTPS client with safe retries and idempotency |
| `client/app.py` | Startup form, session check, owner/worker routing |
| `client/app_shell.py` | Owner navigation and worker mobile tabs |
| `client/owner_views.py` | Panel, Mapy, Opryski, Receptury, Pracownicy, Katalog, Pogoda, Raporty, Ustawienia |
| `client/worker_views.py` | Dziś, Zadanie, Mapa, recipe/PPE/action flow |
| `client/state.py` | Server-backed session view cache; no database |
| `client/widgets.py` | Luna-style reusable controls |
| `client/helpers.py` | Display-only status/date/number/error formatting |
| `client/custom.css` | Responsive visual theme and 60px worker actions |
| `preview/fixtures.py` | Deterministic owner/worker demo payloads |
| `README.md` | Feature matrix and install instructions |
| `IMPORT_MAP.md` | Exact Anvil upload/import/Secrets steps |

- The client exposes every currently callable MVP feature, including inventory
  receipt/balances, catalog source links, recipe copy/export, and read-only OSM
  parcel links. It renders explicit `Planowane` controls only for functionality
  that still has no verified endpoint. It must not create an Anvil database or
  implement a second state machine.

## Source files

- API implementation: `mvp/server.py`
- Models: `mvp/models.py`
- Auth: `mvp/authorization.py`
- Recipes: `mvp/recipes.py`
- Weather: `mvp/weather.py`
- Backups: `mvp/backup.py`
- Client: `uplink/shared/uplink_client.py`
- Anvil package: `anvil_app/`
- Endpoint contract: `uplink/spec/endpoints.md`
- Future work: `OPEN_ISSUES.md`
- Visual reference: `demo/opryski-recipes-demo.html`

## 14. UX/performance implementation status (2026-09-06)

Implemented in the checked-in Anvil package:

- Deterministic client messages for 401/403/404/409 plus transport/offline errors; offline last-known data is read-only.
- Worker recipe compute is cached by `(recipe_id, area_ha)` for the view/session and shows an explicit loading/result state. The MVP remains authoritative for doses and mixing order.
- Catalog requests are bounded to 50 records and expose explicit previous/next controls using the server's `total`, `limit`, and `offset` fields.
- Worker tabs use a dedicated `op-worker-tabs` role and become fixed bottom navigation at mobile widths; primary controls remain 60px on mobile.
- Owner navigation is grouped into Operacje, Gospodarstwo, and System and becomes a responsive two-column layout at <=720px.
- Focus-visible outlines and icon-plus-text status labels are retained; no colour-only safety decision is exposed.

Implemented after the initial handoff:

- `/inventory`, `/inventory/lots`, `/inventory/movements`, and reservation detail are exposed through the Anvil Server Module. Receipt verifies the catalog UUID and exact catalog name; no UUID means no product link.
- `/recipes/{id}/validation`, `/copy`, and `/export?format=json|text` are exposed. Export includes validation findings and report-source pointers; copy preserves the component snapshots but remains a draft.
- Kwatera GeoJSON is validated as a WGS84 Polygon; the returned OpenStreetMap contract is explicitly read-only. It is a reference link, not a spray authorization or buffer calculation.
- Localized Polish/English labels, errors, worker status, and export headings are implemented. Agronomic source text and protocol identifiers are intentionally not machine-translated.

Still planned or deliberately blocked:

- Full offline replay correction and accessibility audit in a real Anvil runtime; the local suite cannot render the hosted Anvil browser.
- Per-product reviewed PPE/prewencja/REI, PDF/A-3, production SMS, OSM editing/buffers, and billing remain roadmap items. Do not invent UI approval for them.

Benchmark method for the next Anvil integration pass:

1. Run `mvp/.venv/bin/python -m pytest -q anvil_app/tests uplink/tests mvp/tests` and `bash uplink/scripts/run_all.sh`.
2. Run `mvp/.venv/bin/python verification/performance_smoke.py`; the 2026-09-06 run used 30 iterations per read path and recorded catalog p95 5.31ms, recipes p95 9.676ms, kwatery p95 2.581ms, inventory p95 2.458ms, and tasks p95 2.171ms on local TestClient/SQLite.
3. Capture response byte sizes (dashboard and catalog) and browser mobile/desktop screenshots at <=720px and >=1024px. Verify no horizontal scroll, keyboard focus visibility, 401/403/404/409 messages, and fixed worker navigation.
4. Treat local targets as guidance only: read p95 <=100ms excluding weather, recipe/task writes <=250ms excluding bcrypt, weather <=2s with loading state. Safety checks and audit events must remain unchanged.

## 15. Verified simulated QA artifacts (2026-09-06)

- `verification/full-simulated-staff-e2e-20260906.json` — owner/worker lifecycle, double confirmation, green weather gate, inventory reservation/deduction, cancellation, dry-run SMS, GeoJSON/OSM, and catalog URL checks. Real SMS: false.
- `verification/ten-recipe-qa-20260906.json` — ten isolated draft recipes, ten copies, twice-identical validation responses, JSON/text export, real catalog UUID/name/detail URL evidence. This is not a production recipe approval set.
- `verification/performance-smoke-20260906.json` — repeatable local read-path timings; it does not represent production capacity.
- `verification/UI-PERFORMANCE-RESEARCH-20260906.md` — local UX/performance recommendations, official references to re-check, and explicit hosted-Anvil limitations.
- Functional gate: `123 passed` MVP tests, `7 passed` Anvil client tests, `compileall=ok`, `bash uplink/scripts/run_all.sh` `28/28 passed`.

## 16. Hosted Anvil QA handoff (2026-09-06)

This addendum records what was actually verified against the published app at
`https://jaunty-infamous-seal.anvil.app/`. It supersedes any earlier statement
that a browser session, production MVP, SMS provider, or local `anvil_app/`,
`mvp/`, `uplink/`, or `verification/` tree was exercised from this checkout.

### Test results

| Check | Result | Notes |
|---|---|---|
| Published app GET | PASS | HTTP 200; final URL is the published Anvil URL; page title is `Opryski Recipes`; startup form metadata is `Form1`. |
| Published manifest | PASS | `/_/manifest.json` returned HTTP 200. |
| Anvil runtime JavaScript | PASS | `runner2.bundle.js` returned HTTP 200. |
| Anvil runtime CSS | PASS | `runner-v3.min.css` returned HTTP 200. |
| App theme asset | PASS | `/_/theme/theme.css` returned HTTP 200. |
| Checkout validation | PASS | `anvil --json validate .`: 18 files valid. |
| Server syntax | PASS | `python -m py_compile server_code/api.py server_code/uplink_client.py`. |
| Gateway mock suite | PASS | All 27 server callables covered across the mock run plus the logout follow-up; 32 mocked HTTP calls and 9 expected error cases. |
| Client helper/state smoke | PASS | Result normalization, status labels, task/recipe state, and catalog paging smoke checks passed. |
| Browser login and role workflows | NOT RUN | No browser automation or test credentials were available in this environment. |
| Real MVP/Uplink calls | NOT RUN | The published app's Anvil secret and external MVP base URL cannot be inspected from the checkout. |

### Fix before accepting the deployment

1. Set and verify the Anvil secret `MVP_BASE_URL`, then run one real owner
   login and one worker login against a disposable test account. Confirm the
   external API allows the published Anvil origin (CORS) and that every path in
   `server_code/api.py` matches the deployed MVP contract.
2. Fix `mvp_login`: if the token is accepted but `/auth/me` fails, the function
   currently returns success with a fallback user. It should clear the token
   and return an explicit failure, or return a clearly marked partial-session
   result; otherwise the client can show an owner shell with an invalid session.
3. Add a real browser QA pass at desktop and <=720px mobile widths: login,
   owner/worker routing, create kwatera, create recipe, create/dispatch task,
   worker confirmation, owner authorization, weather safety gate, cancellation,
   catalog paging, and inventory receipt. Capture screenshots and console/network
   errors in the release record.
4. The current UI does not expose every gateway callable. Add user-facing flows
   for recipe validation/copy/export and inventory/lots/movements/reservation/
   receipt, or label those operations as deliberately unavailable in this
   release. Do not claim they are covered by the UI until tested.
5. Add retry/idempotency handling to `server_code/uplink_client.py` if the MVP
   contract requires it; the current client performs one HTTP request and has
   no retry policy. Keep retries limited to safe/idempotent operations and do
   not duplicate writes.
6. Replace the stale historical references above with the actual Anvil source
   package when those artifacts are imported, or keep this addendum as the
   authoritative checkout-level QA record. The current checkout contains
   `client_code/`, `server_code/`, `theme/`, and `anvil.yaml`, but not the old
   `anvil_app/`, `mvp/`, `uplink/`, or `verification/` paths.
7. Align the PWA manifest name with the product name. The live manifest still
   reports `M3 App 1` while the page title and app metadata report `Opryski
   Recipes`; verify the intended Anvil package/display-name setting before
   release.

### Release decision

**Deployment smoke: PASS. Production acceptance: BLOCKED pending the real
MVP_BASE_URL/session/browser checks above.**
