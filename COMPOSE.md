# Docker Compose scopes

PA Jarvis provides a full-stack Compose file and smaller files for focused local testing.

## Full stack

From the repository root:

```powershell
docker compose -f "02 Source/compose.app.yaml" up --build
```

The full stack creates the shared Docker network named `pa-jarvis-dev`.

## Storage only

Storage also creates `pa-jarvis-dev`, allowing independently started services to resolve it as `storage`:

```powershell
docker compose -f "02 Source/Storage/compose.storage.yaml" up --build
```

## Scripts only

Start Storage first because Scripts sends execution events to `http://storage:8004`:

```powershell
docker compose -f "02 Source/Storage/compose.storage.yaml" up -d
docker compose -f "04 Scripts/compose.scripts.yaml" up --build
```

The Scripts media jobs also require the untracked Google service-account file at
`02 Source/Tools/credentials/service-account.json`, which is mounted read-only into the container.

## Analytics only

Analytics connects directly to PostgreSQL using the Storage `.env` file; the Storage HTTP service does not need to run:

```powershell
docker compose -f "05 Analytics/analytics_dashboard_fastpy/compose.analytics.yaml" up --build
```

The dashboard is available at `http://localhost:8006` and the static UI prototype at `http://localhost:8006/static/dashboard_demo.html`.

## Frontend only

This starts the compiled React UI without the backend APIs:

```powershell
docker compose -f "02 Source/Frontend/njs_frontend/compose.frontend.yaml" up --build
```

The frontend is available at `http://localhost:5173`. Chat/API operations require the backend stack.
