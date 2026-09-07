# Remaining Issues Handoff — Opryski Recipes Anvil Frontend

Date: 2026-09-07

## Current source state

The current Anvil source is the frontend checkout under `anvil.yaml`,
`client_code/`, `server_code/`, and `theme/`. The latest local auto-sync
commit includes the Skulpt runtime fix and the M3 component namespace fix.

The client helper no longer imports `typing.Any` or uses `Any` annotations;
Anvil client Python runs under Skulpt, where `typing` is unavailable. Form1
now references the dependency's actual component paths:
`m3._Components.TextInput.TextBox` and `m3._Components.TextInput.TextArea`.
Text inputs are coerced to strings before JSON parsing or string methods so
Anvil's M3 type metadata validates cleanly. These changes do not alter
authentication, MVP routes, recipe calculations, weather decisions, inventory
rules, or task transitions.

## Local verification

- `python tests/test_server_code_contract.py`: **10 tests passed**.
- All 30 registered server callables are exercised by the contract harness.
- Python compilation: **PASS**.
- Client `typing`/`Any` scan: **PASS**.
- Duplicate components: **none**.
- Missing click-handler components: **none**.
- Recipe, inventory, and worker controls: **present**.
- `git diff --check`: **PASS**.
- `anvil --json validate .`: **18 files valid**.

## Hosted state

Published URL: `https://jaunty-infamous-seal.anvil.app/`

- Application GET: **HTTP 200**.
- Manifest GET: **HTTP 200**.
- The live manifest still reports `M3 App 1` rather than `Opryski Recipes`.
- The corrected helper and M3 namespace have not been published to the hosted
  app yet.
- Authenticated owner/worker browser QA has not been run.
- `MVP_BASE_URL`, MVP CORS, and real Uplink requests are not verified.

## Current runtime blocker and publish blocker

The previously observed hosted runtime error was:

```text
ModuleNotFoundError: No module named 'm3._Components.TextBox'
```

The local source correction is complete. The dependency contains TextBox and
TextArea under `m3._Components.TextInput`, so the old direct component paths
must not be restored.

An attempted Anvil CLI sync/publish was rejected:

```text
Access denied to app: GG6QEJZ4UB72TQJU
```

The app owner must open the Anvil IDE, sync/import this source, and publish
the corrected version. After publishing, repeat desktop and mobile smoke at
1280x900 and 390x844 (or any width at or below 720px).

## Required before production acceptance

1. Publish the Skulpt-compatible helper fix.
2. Confirm the app loads without a runtime error screen on desktop and mobile.
3. Configure the Anvil secret `MVP_BASE_URL` and verify MVP CORS for the
   published Anvil origin.
4. Run disposable owner and worker live workflows, including recipe,
   inventory, weather-gated authorization, and task state transitions.
5. Change the published manifest/PWA name to `Opryski Recipes` and verify
   `/_/manifest.json` reports the corrected name.
6. Capture screenshots, browser console errors, and failed network requests
   in the release record.

Do not report production acceptance as PASS until all six items are complete.
