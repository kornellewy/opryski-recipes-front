# Opryski Recipes — OPEN ISSUES

This frontend deliberately keeps the following capabilities visible as
`Planowane` and disabled until the external MVP exposes reviewed, server-side
contracts. The Anvil UI must not simulate or authorize any of them:

- PIORiN PDF/A-3 export.
- Inventory reserve, deduct, and release operations.
- Reviewed PPE, prewencja, and REI calculations.
- Production SMS and GSM-7 fallback.
- Bee, public-road, and water-buffer checks.
- OSM editing and spray-buffer editing.
- Recipe or kwatera update/delete.
- Offline replay correction.
- Billing and multi-farm administration.

The external FastAPI MVP remains the source of truth for authentication,
weather suitability, recipe calculations, inventory rules, and task
transitions. Do not enable a control here until its MVP endpoint, authorization
rules, idempotency contract, and live browser flow are verified.
