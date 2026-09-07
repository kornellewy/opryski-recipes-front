# Handoff for the Python Anvil frontend coding agent

This file is the implementation contract and release handoff for the Anvil
frontend. Read it before writing forms or server calls. The external FastAPI
MVP is the source of truth for auth, recipes, weather, task state, inventory,
and audit records; it is not included in this checkout.

## 1. Product and architecture

`opryski-recipes` is a Polish orchard-spraying management app for sadownicy.

- **Anvil frontend**: `anvil.yaml`, `client_code/`, `server_code/`, and `theme/`
  call the MVP through the Server Module gateway. Do not duplicate auth,
  weather thresholds, recipe calculations, catalog data, or transition rules in
  Anvil.
The gateway stores the JWT only in `anvil.server.session`; never place the MVP
secret or passwords in client UI. Set `MVP_BASE_URL` as an Anvil secret and
configure the published Anvil origin in the MVP CORS settings.

```python
from anvil import server

me = server.call("mvp_login", email, password)
dashboard = server.call("mvp_dashboard")
```

## 2. Owner desktop UI

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
- [x] `python -m unittest -q tests/test_server_code_contract.py` reports eight passing gateway tests.

## 13. Authoritative Anvil source layout

This checkout contains the complete frontend source under `anvil.yaml`,
`client_code/`, `server_code/`, and `theme/`. The external FastAPI MVP remains
the source of truth for authentication, safety decisions, calculations,
weather, inventory, and task transitions. No separate backend source tree is
part of this repository.

The frontend exposes server results for recipe validation/copy/export,
inventory balances/lots/receipt/movements/reservation details, and the worker
mobile flow. Unsupported capabilities remain disabled as `Planowane`.

## 14. Runtime and verification scope

- The UI does not calculate chemical doses, mixing order, weather suitability,
  karencja, or task-transition legality.
- Worker tasks use `GET /workers/me/tasks`; worker action buttons mirror the
  server states `dispatched`, `worker-confirmed`, `owner-approved`,
  `execution-started`, and `execution-completed`.
- Yellow and red weather statuses never enable owner authorization.
- Real SMS/GSM-7, reviewed PPE/prewencja/REI, buffer checks, OSM editing,
  update/delete, offline replay correction, billing, and multi-farm admin are
  still visibly planned/unavailable.

The separate MVP checkout and its backend test suite were not available in this
frontend environment, so no backend test count is claimed here.

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
| Gateway mock suite | PASS | 30 callable registrations covered by the eight-test contract harness, including login rollback, retry, idempotency, export validation, weather snapshot, and route mapping. |
| Client helper/state smoke | PASS | Result normalization, status labels, task/recipe state, and catalog paging smoke checks passed. |
| Browser login and role workflows | NOT RUN | No browser automation or test credentials were available in this environment. |
| Real MVP/Uplink calls | NOT RUN | The published app's Anvil secret and external MVP base URL cannot be inspected from the checkout. |

### Fix before accepting the deployment

1. Set and verify the Anvil secret `MVP_BASE_URL`, then run one real owner
   login and one worker login against a disposable test account. Confirm the
   external API allows the published Anvil origin (CORS) and that every path in
   `server_code/api.py` matches the deployed MVP contract.
2. **Resolved in the 2026-09-07 pass:** `mvp_login` now clears the token and
   returns explicit failure when `/auth/me` cannot validate it.
3. Add a real browser QA pass at desktop and <=720px mobile widths: login,
   owner/worker routing, create kwatera, create recipe, create/dispatch task,
   worker confirmation, owner authorization, weather safety gate, cancellation,
   catalog paging, and inventory receipt. Capture screenshots and console/network
   errors in the release record.
4. **Resolved in the 2026-09-07 pass:** owner-facing recipe validation,
   copy/export, and inventory balances/lots/receipt/movements/reservation
   controls now exist. They still require real MVP/browser testing.
5. **Resolved in the 2026-09-07 pass:** read retries and mutation
   idempotency headers are implemented in `server_code/uplink_client.py`.
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

## 17. Implementation pass (2026-09-07)

The requested frontend implementation plan is now applied to this checkout:

- `mvp_login` sends OAuth2-compatible `username`, `password`, and
  `grant_type=password` fields, validates `/auth/me`, and clears the Anvil
  session before returning failure when validation fails.
- `uplink_client` retries only read requests (`GET`, `HEAD`, `OPTIONS`) up to
  three attempts for transport/status-0 and transient 5xx failures. Mutations
  are single-attempt operations with one generated `Idempotency-Key`; login is
  explicitly excluded from that header.
- Owner navigation now includes recipe tools for validation, copy, and export,
  plus a Magazyn view for balances, lots/receipt, movements, and reservation
  details. Any unsupported report work remains visibly `Planowane`.
- Worker refresh uses the `mvp_worker_my_tasks` callable and scoped
  `GET /workers/me/tasks`. Authorization remains disabled unless the server
  task is worker-confirmed and the server weather status is explicitly
  green/safe.
- Task actions map to explicit MVP routes rather than a generic action path;
  recipe compute passes `area_ha` as a query parameter; catalog products use
  `/catalog/products`; inventory lots/receipt use `/inventory` and
  `POST /inventory/lots`.
- `mvp_server_weather_snapshot` runs before task creation and uses a bounded
  retryable POST without an idempotency key because the endpoint is read-only.
- Kwatera creation includes `area_ha` and `polygon_geojson`.
- `README.md` now documents the authoritative Anvil layout and explicitly says
  that `anvil_app/`, `mvp/`, `uplink/`, and `verification/` are not part of this
  frontend checkout.

Verification for this pass:

- `anvil --json validate .`: **18 files valid**.
- Python compilation for `server_code/api.py`, `server_code/uplink_client.py`,
  and `client_code/Form1/__init__.py`: **PASS**.
- Mock gateway contract: **PASS** — 30 callable functions counted; OAuth2 login,
  failed `/auth/me` rollback, three-attempt read retry, mutation idempotency,
  no-retry login/mutation behavior, weather-snapshot retry, and corrected route
  mapping exercised.
- Static Form contract: **PASS** — no duplicate `anvil:name` values, every
  click handler has a matching component, recipe/inventory/worker controls are
  present, and no credential literals are committed.
- `git diff --check`: **PASS**.
- Local MVP pytest/API smoke suite: **not available in this checkout**.
- Hosted browser acceptance: still pending a disposable owner/worker account
  and a real Anvil browser session against the configured MVP URL.
- Hosted GET/manifest smoke is reachable (HTTP 200), but the current published
  bundle does not yet contain the newly added `Narzędzia receptury` label or the
  `/workers/me/tasks` contract in its serialized client bundle. Push or publish
  this checkout in Anvil, then repeat the manifest and browser checks before
  treating the hosted target as this implementation pass.

## 18. MVP contract correction pass (2026-09-07)

The frontend gateway now matches the corrected MVP contract:

- Exactly 30 callables are registered, including `mvp_worker_me`,
  `mvp_worker_my_tasks`, and `mvp_server_weather_snapshot`.
- Task actions map to the explicit MVP transition routes; no generic
  `/actions/{action}` path remains.
- Recipe compute sends `area_ha` as a query parameter.
- Catalog products use `/catalog/products`.
- Inventory lots read from `/inventory`; receipts post to `/inventory/lots`.
- Task creation obtains a retryable server weather snapshot before posting the
  task. The snapshot is treated as read-only and receives no idempotency key.
- Kwatera creation sends `area_ha` and `polygon_geojson`.

Verification: `python -m unittest -q tests/test_server_code_contract.py`
reports **8 tests passing**; Python compilation and `git diff --check` pass;
`anvil --json validate .` reports **18 files valid** in this environment.
