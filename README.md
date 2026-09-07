# About This [Anvil](https://anvil.works/?utm_source=github:app_README) App

## Opryski Recipes frontend

This checkout contains the Anvil UI for the external `opryski-recipes` MVP.
The app intentionally has no local Users table or duplicated spray rules: all
authentication, weather suitability, recipe calculations, compliance snapshots,
and task transitions are performed by the MVP through the `api` Server Module.

In the Anvil IDE, add the secret `MVP_BASE_URL` with the published HTTPS URL of
the MVP. The Server Modules `api` and `uplink_client` keep the JWT in
`anvil.server.session` and call the MVP with an Authorization header. Test the
owner and worker workflows from the startup Form after the MVP is reachable.

The UI keeps unavailable endpoints visible as disabled `Planowane` controls and
does not claim support for PIORiN PDF/A-3 export, inventory deductions,
prewencja/REI, SMS, buffer checks, or billing.
The complete roadmap is listed in `OPEN_ISSUES.md`; the settings view links to
that file and does not attach handlers to any unavailable control.

### Authoritative source layout

This repository is the Anvil frontend package. The authoritative files are:

- `anvil.yaml` — app metadata, startup form, dependency, and runtime settings
- `client_code/` — `Form1` and reusable card Forms
- `server_code/api.py` — server-callable gateway to the external MVP
- `server_code/uplink_client.py` — server-only HTTP, retry, JWT, and idempotency handling
- `theme/` — app theme parameters, CSS, and handoff assets

The external FastAPI MVP remains the source of truth for authentication,
safety decisions, recipe calculations, weather, inventory, and spray-task
transitions. This checkout intentionally does not contain `anvil_app/`, `mvp/`,
`uplink/`, or `verification/` directories.

Owner coverage includes recipe validation/copy/export tools and inventory
balances, lots/receipt, movements, and reservation details. Add the Anvil secret
`MVP_BASE_URL` before testing those flows against a disposable MVP account.

Worker tasks are scoped to `GET /workers/me/tasks` through the
`mvp_worker_my_tasks` Server Module callable. The worker mobile tabs are
`Dziś`, `Zadanie`, and `Mapa`; action buttons mirror server states only. The
owner authorization control remains unavailable unless the server reports an
explicit green/safe weather status.

Task transitions use the MVP's explicit routes (`dispatch`, `worker-confirm`,
`owner-authorize`, `execution-started`, `execution-completed`, and `cancel`).
Recipe compute uses `POST /recipes/{id}/compute?area_ha=...`; catalog products
use `/catalog/products`; inventory lots and receipts use `/inventory` and
`POST /inventory/lots`. Task creation obtains a retryable server weather
snapshot from the selected kwatera coordinates
(`POST /weather/server-snapshot?lat=...&lon=...`) before posting the task. The
snapshot is included in the task payload with `t_source=server`.

The login gateway sends OAuth2-compatible `username`, `password`, and
`grant_type=password` fields, validates `/auth/me` before success, and clears
the session if validation fails. Read-only requests retry bounded transient
failures; mutations receive one generated `Idempotency-Key` and are never
retried. Login itself never receives an idempotency key.

### Build web apps with nothing but Python.

The app in this repository is built with [Anvil](https://anvil.works?utm_source=github:app_README), the framework for building web apps with nothing but Python. You can clone this app into your own Anvil account to use and modify.

Below, you will find:
- [How to open this app](#opening-this-app-in-anvil-and-getting-it-online) in Anvil and deploy it online
- Information [about Anvil](#about-anvil)
- And links to some handy [documentation and tutorials](#tutorials-and-documentation)

## Opening this app in Anvil and getting it online

### Cloning the app

Go to the [Anvil Editor](https://anvil.works/build?utm_source=github:app_README) (you might need to sign up for a free account) and click on “Clone from GitHub” (underneath the “Blank App” option):

<img src="https://anvil.works/docs/version-control/img/git/clone-from-github.png" alt="Clone from GitHub"/>

Enter the URL of this GitHub repository. If you're not yet logged in, choose "GitHub credentials" as the authentication method and click "Connect to GitHub".

<img src="https://anvil.works/docs/version-control/img/git/clone-app-from-git.png" alt="Clone App from Git modal"/>

Finally, click "Clone App".

This app will then be in your Anvil account, ready for you to run it or start editing it! **Any changes you make will be automatically pushed back to this repository, if you have permission!** You might want to [make a new branch](https://anvil.works/docs/version-control?utm_source=github:app_README).

### Running the app yourself:

Find the **Run** button at the top-right of the Anvil editor:

<img src="https://anvil.works/docs/img/run-button-new-ide.png"/>


### Publishing the app on your own URL

Now you've cloned the app, you can [deploy it on the internet with two clicks](https://anvil.works/docs/deployment/quickstart?utm_source=github:app_README)! Find the **Publish** button at the top-right of the editor:

<img src="https://anvil.works/docs/deployment/img/environments/publish-button.png"/>

When you click it, you will see the Publish dialog:

<img src="https://anvil.works/docs/deployment/img/quickstart/empty-environments-dialog.png"/>

Click **Publish This App**, and you will see that your app has been deployed at a new, public URL:

<img src="https://anvil.works/docs/deployment/img/quickstart/default-public-environment.png"/>

That's it - **your app is now online**. Click the link and try it!

## About Anvil

If you’re new to Anvil, welcome! Anvil is a platform for building full-stack web apps with nothing but Python. No need to wrestle with JS, HTML, CSS, Python, SQL and all their frameworks – just build it all in Python.

<figure>
<figcaption><h3>Learn About Anvil In 80 Seconds👇</h3></figcaption>
<a href="https://www.youtube.com/watch?v=3V-3g1mQ5GY" target="_blank">
<img
  src="https://anvil-website-static.s3.eu-west-2.amazonaws.com/anvil-in-80-seconds-YouTube.png"
  alt="Anvil In 80 Seconds"
/>
</a>
</figure>
<br><br>

[![Try Anvil Free](https://anvil-website-static.s3.eu-west-2.amazonaws.com/mark-complete.png)](https://anvil.works?utm_source=github:app_README)

To learn more about Anvil, visit [https://anvil.works](https://anvil.works?utm_source=github:app_README).

## Tutorials and documentation

### Tutorials

If you are just starting out with Anvil, why not **[try the 10-minute Feedback Form tutorial](https://anvil.works/learn/tutorials/feedback-form?utm_source=github:app_README)**? It features step-by-step tutorials that will introduce you to the most important parts of Anvil.

Anvil has tutorials on:
- [Building Dashboards](https://anvil.works/learn/tutorials/data-science#dashboarding?utm_source=github:app_README)
- [Multi-User Applications](https://anvil.works/learn/tutorials/multi-user-apps?utm_source=github:app_README)
- [Building Web Apps with an External Database](https://anvil.works/learn/tutorials/external-database?utm_source=github:app_README)
- [Deploying Machine Learning Models](https://anvil.works/learn/tutorials/deploy-machine-learning-model?utm_source=github:app_README)
- [Taking Payments with Stripe](https://anvil.works/learn/tutorials/stripe?utm_source=github:app_README)
- And [much more....](https://anvil.works/learn/tutorials?utm_source=github:app_README)

### Reference Documentation

The Anvil reference documentation provides comprehensive information on how to use Anvil to build web applications. You can find the documentation [here](https://anvil.works/docs/overview?utm_source=github:app_README).

If you want to get to the basics as quickly as possible, each section of this documentation features a [Quick-Start Guide](https://anvil.works/docs/overview/quickstarts?utm_source=github:app_README).
