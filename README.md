# PA-JARVIS

PA-JARVIS is a personal AI assistant platform with a React chat interface, a
FastAPI-based multi-service backend, pluggable large language model (LLM)
providers, personal productivity tools, and an analytics display. 
It is intended to be used by anyone who wants to setup an enterprise-style 
personal AI assistant that can be deployed in a self-hosted, cloud-native or 
hybrid architecure, and integrate with digital personal systems and assets.

## What PA-JARVIS Does

- Provides a browser-based conversational assistant.
- Routes requests through a master agent to specialized sub-agents.
- Supports Gemini, Groq, and local Ollama/Qwen LLM providers.
- Stores configuration, tool data, and service events in PostgreSQL.
- Has tools to integrate with Google Calendar, Gmail, and Google Drive using OAuth.
- Displays tasks, shopping items, calendar events, and media on dashboard and TV
- Runs as 8 containerized services on a Kubernetes cluster and with Docker Compose.

## Architecture

| Service | Purpose | Local port |
| --- | --- | ---: |
| Frontend | React chat interface served by Nginx | `5173` |
| Backend | Public chat API and request router | `8000` |
| Agents | Master-agent orchestration | `8001` |
| LLM | Gemini, Groq, and Ollama/Qwen provider access | `8002` |
| Tools | Personal, planning, communication, and internet tools | `8003` |
| Storage | PostgreSQL access and event logging API | `8004` |
| Scripts | Scheduled synchronization and utility jobs | `8005` |
| Analytics | Dashboard and TV display | `8006` |

The browser sends chat requests to the frontend's Nginx proxy. Requests then
flow through Backend, Agents, LLM, and Tools. Storage provides shared persistence,
while Scripts and Analytics use the same PostgreSQL data and shared media volume.

## Prerequisites

The recommended local setup uses Docker Compose. Install or provide:

- Git.
- Docker Desktop, or Docker Engine with the Compose plugin.
- A PostgreSQL server reachable from the containers.
- One supported LLM provider:
  - a Gemini API key;
  - a Groq API key; or
  - an Ollama server with a compatible Qwen model.
- Google OAuth credentials only if using the Calendar, Gmail, or Drive tools.

Docker builds the application runtimes. Python 3.13 or later and Node.js 22 or
later are needed only when running services directly outside Docker.

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/arushparulinc/pa-jarvis.git
Set-Location pa-jarvis
```

### 2. Prepare PostgreSQL

Create a development role and database. The following commands prompt for the
application user's password instead of placing it in shell history:

```powershell
createuser -U postgres --pwprompt pa_jarvis_app_dev
createdb -U postgres --owner=pa_jarvis_app_dev pa-jarvis-dev
```

Create the database objects and seed the required configuration:

```powershell
psql -U postgres -v target_db="pa-jarvis-dev" -v pgsql_user="pa_jarvis_app_dev" -f "02 Source/Storage/pgsql/pa-jarvis-db-create.sql"
psql -U postgres -v target_db="pa-jarvis-dev" -f "02 Source/Storage/pgsql/pa-jarvis-db-inserts.sql"
```

The account running these scripts must be allowed to create schemas and assign
the grants defined by the SQL files.

### 3. Configure the environment

Create `02 Source/.env`. This file is intentionally ignored by Git because it
contains secrets. A minimal Gemini-based configuration is:

```dotenv
PGSQL_HOSTNAME=host.docker.internal
PGSQL_PORT=5432
PGSQL_USER=pa_jarvis_app_dev
PGSQL_PASSWORD=replace-with-your-database-password
PGSQL_DBNAME=pa-jarvis-dev

PRIMARY_PROVIDER=gemini
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

SCRIPTS_TIME_ZONE=America/Toronto
AK_DATA_HOST_DIR=../data
```

`host.docker.internal` normally reaches a host-based database from Docker
Desktop. Use a hostname reachable from Docker if PostgreSQL runs elsewhere.

To use Groq, set `PRIMARY_PROVIDER=groq` and `GROQ_API_KEY`. To use Ollama/Qwen,
set `PRIMARY_PROVIDER=qwen`, `OLLAMA_HOST`, and `OLLAMA_MODEL`. Review the
`OLLAMA_HOST` value in `02 Source/compose.app.yaml` as well, because the Compose
service currently supplies that value to the LLM container.

Optional Google integrations use these variables:

```dotenv
AK_GOOGLE_CLIENT_ID=replace-with-your-client-id
AK_GOOGLE_CLIENT_SECRET=replace-with-your-client-secret
AK_GOOGLE_REFRESH_TOKEN=replace-with-your-refresh-token
AK_GDRIVE_ROOT_FOLDER_ID=replace-with-your-folder-id
AK_PICS_GDRIVE_ROOT_FOLDER_ID=replace-with-your-pictures-folder-id
```

Never commit `.env`, OAuth credentials, API keys, or database passwords.

### 4. Start PA-JARVIS

From the repository root, build and start all eight services:

```powershell
docker compose -f "02 Source/compose.app.yaml" up --build
```

Use detached mode after confirming that the services start successfully:

```powershell
docker compose -f "02 Source/compose.app.yaml" up --build --detach
```

## Using PA-JARVIS

Open the following URLs after the stack starts:

| Product or endpoint | URL |
| --- | --- |
| Chat interface | <http://localhost:5173> |
| Analytics dashboard | <http://localhost:8006> |
| TV display | <http://localhost:8006/tv> |
| Backend API documentation | <http://localhost:8000/docs> |

Enter a request in the chat interface, for example:

- `Help me plan my day.`
- `Add milk to my shopping list.`
- `What tasks are still open?`

Available actions depend on the configured LLM provider, database seed data, and
optional Google integrations.

### Verify service health

```powershell
8000..8006 | ForEach-Object {
    Invoke-RestMethod "http://localhost:$_/health"
}
```

The frontend does not expose a health API; verify it by opening
<http://localhost:5173>.

### Stop the application

```powershell
docker compose -f "02 Source/compose.app.yaml" down
```

See [COMPOSE.md](COMPOSE.md) for commands that run individual services or smaller
service groups.

## Troubleshooting

- **A service cannot connect to PostgreSQL:** confirm `PGSQL_HOSTNAME`, the
  database port, credentials, firewall rules, and PostgreSQL client access rules.
- **Chat requests fail:** check that the selected provider has a valid API key or
  that the configured Ollama server and model are available.
- **Analytics does not start:** verify that the database scripts completed and
  the configured database is reachable.
- **Google-backed tools fail:** confirm the OAuth client, refresh token, scopes,
  and Drive folder IDs.
- **A port is already in use:** stop the conflicting process or change the host
  port in `02 Source/compose.app.yaml`.

Inspect container status and logs with:

```powershell
docker compose -f "02 Source/compose.app.yaml" ps
docker compose -f "02 Source/compose.app.yaml" logs --follow
```

## Repository Structure

```text
pa-jarvis/
|-- 01 Documents/       Architecture, engineering, operations, and portfolio docs
|-- 02 Source/          Frontend and backend application services
|-- 03 Infrastructure/  Kubernetes, Helm, Argo CD, and Traefik configuration
|-- 04 Scripts/         Scheduled and utility scripts service
|-- 05 Analytics/       Analytics dashboard and TV display service
|-- 06 Assets/          Images, icons, and diagrams
|-- .github/workflows/  GitHub Actions workflows
|-- CHANGELOG.md         Release history and upcoming changes
|-- COMPOSE.md           Focused Docker Compose instructions
|-- LICENSE              MIT license
`-- README.md            Project overview and usage guide
```

Project delivery material, demonstrations, and supporting evidence belong under
`01 Documents/07 Portfolio/`, not in this product README.

## Security Notes

- Use least-privilege database and OAuth accounts.
- Keep development and production credentials separate.
- Store production secrets in a secrets manager rather than environment files.
- Review exposed ports and network access before deploying outside a trusted
  development environment.

## License

PA-JARVIS is licensed under the [MIT License](LICENSE).

## Support and Contact

Use [GitHub Issues](https://github.com/arushparulinc/pa-jarvis/issues) to report a
bug, request a feature, or ask a project-specific question.
