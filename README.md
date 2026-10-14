# PA-JARVIS

PA-JARVIS is a personal AI assistant platform with a React chat interface, a
FastAPI-based multi-service backend, pluggable large language model (LLM)
providers, personal productivity tools, and an analytics display.
It is intended for anyone who wants to set up an enterprise-style personal AI
assistant that can be deployed in a self-hosted, cloud-native, or hybrid
architecture and integrated with personal digital systems and assets.

## What PA-JARVIS Does

- Provides a browser-based conversational assistant.
- Routes requests through a master agent to specialized sub-agents.
- Supports Gemini, Groq, and local Ollama/Qwen LLM providers.
- Stores configuration, tool data, and service events in PostgreSQL.
- Has tools to integrate with Google Calendar, Gmail, and Google Drive using
  OAuth.
- Displays tasks, shopping items, calendar events, and media on dashboard and TV.
- Runs as eight containerized services on Kubernetes or with Docker Compose.

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

Chat requests are routed from the React frontend through the Backend API to the
Agents service, which orchestrates LLM interactions and invokes tools as
required. The Storage service provides database access, while Scripts handles
scheduled jobs and Analytics serves dashboard views.

## Prerequisites for running locally

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

## Prerequisites for running on a production server

The production deployment is designed for a self-hosted or cloud-based Kubernetes
environment. Provide and configure:

- An Ubuntu Server host with K3s installed.
- `kubectl` access to the target Kubernetes cluster.
- Argo CD installed and connected to this Git repository.
- Environment-specific Argo CD Applications for the development and production
  Helm releases. These Applications are configured externally and are not stored
  in this repository.
- The Traefik ingress controller. K3s includes Traefik by default unless it is
  disabled during installation.
- Access to the Helm chart under
  `03 Infrastructure/Kubernetes/helm/pa-jarvis`.
- A PostgreSQL server reachable from the Kubernetes workloads.
- The Kubernetes Secrets described in the deployment section below.
- Access to the PA-JARVIS images in GHCR. Configure an image-pull Secret if the
  container packages are private.
- A persistent host directory matching `sharedData.hostPath` in the selected
  Helm values file.
- Network and firewall rules that allow the cluster to reach PostgreSQL, the
  configured LLM providers, and any enabled Google services.

Public internet access is optional. If enabled, configure:

- Public DNS `A` and, when applicable, `AAAA` records for the chat and analytics
  hostnames in the selected Helm values file.
- A stable public IP address or a dynamic DNS mechanism.
- A stable private IP address for the server receiving inbound traffic.
- Inbound TCP port 80 and 443 forwarding to the Traefik ingress endpoint.
- Firewall rules that permit the required HTTP and HTTPS traffic.
- Traefik ingress rules that send `/api` traffic to Backend, other chat traffic
  to Frontend, and the analytics hostname to Analytics.

Some home networks have an ISP-supplied modem/router in front of a separate
private-network router. In this double-NAT arrangement, configure forwarding on
the ISP gateway—potentially through the provider's management application—to the
private router, then configure the private router to forward ports 80 and 443 to
the production server. The exact steps depend on the network equipment and ISP.
Inbound forwarding may not work when the connection uses carrier-grade NAT;
contact the ISP or use a secure tunnel if no public address is available.

Traefik uses Let's Encrypt to obtain TLS certificates. The current configuration
uses the ACME HTTP-01 challenge on the `web` entry point, so public DNS must
resolve to the ingress and TCP port 80 must remain reachable during certificate
issuance and renewal. HTTPS application traffic is served on TCP port 443.

> **Warning:** PA-JARVIS does not currently implement end-user authentication.
> Publicly exposing the Frontend also exposes its chat API. Use network-level
> access controls, an authenticated reverse proxy, a VPN, or another appropriate
> protection before enabling public access.

The production Traefik configuration can optionally forward the development
hostname to the externally configured development server through a Kubernetes
Service and EndpointSlice. Enable this only when the production cluster can
securely reach that server and public development access is intentional.

## Installation - Local

### 1. Clone the repository

```powershell
git clone https://github.com/arushparulinc/pa-jarvis.git
Set-Location pa-jarvis
```

### 2. Prepare PostgreSQL

Install PostgreSQL on a local server or cloud host, and record its hostname or IP
address and port.

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

### 3. Configure the local environment

Create `02 Source/.env`. This file is intentionally ignored by Git because it
contains secrets. A minimal Gemini-based configuration is:

```dotenv
PGSQL_HOSTNAME=replace-with-your-postgres-hostip
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

### 4. Start PA-JARVIS locally

From the repository root, build and start all eight services:

```powershell
docker compose -f "02 Source/compose.app.yaml" up --build
```

Use detached mode after confirming that the services start successfully:

```powershell
docker compose -f "02 Source/compose.app.yaml" up --build --detach
```

### 5. Verify service health

```powershell
8000..8006 | ForEach-Object {
    Invoke-RestMethod "http://localhost:$_/health"
}
```

The frontend does not expose a health API; verify it by opening
<http://localhost:5173>.

### 6. Stop the application

```powershell
docker compose -f "02 Source/compose.app.yaml" down
```

See [COMPOSE.md](COMPOSE.md) for commands that run individual services or smaller
service groups.

## Using PA-JARVIS

Open the following URLs after the stack starts:
(Optionally, open chat web page if using your own domain)

| Product or endpoint | URL |
| --- | --- |
| Chat interface | <http://localhost:5173> |
| Analytics dashboard | <http://localhost:8006> |
| TV display | <http://localhost:8006/tv> |
| Backend API documentation | <http://localhost:8000/docs> |

Enter a request in the chat interface, for example:

- `Create 1 hr calendar event for Yoga Class tomorrow at 6 pm`
- `Add milk to my shopping list.`
- `What to-do tasks are still open?`
- `List files in my google drive folder 'xyz' and email it to abc@gmail.com`

Available actions depend on the configured LLM provider, database seed data, and
optional Google integrations.


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

If PostgreSQL and the Storage service are available, use these tables for
troubleshooting:

| Table | Contents |
| --- | --- |
| `logging.service_events` | Events recorded by application services |
| `logging.llm_calls` | LLM calls |
| `logging.tool_calls` | Tool calls |
| `logging.script_events` | Script executions |

## Deploying to a production server with GitHub Actions and Argo CD

PA-JARVIS uses a GitOps delivery flow. GitHub Actions builds immutable container
images and updates the desired image tags in Git; Argo CD detects approved Git
changes and synchronizes the Helm release to the appropriate Kubernetes cluster.

The environment-specific Argo CD Applications that track the PA-JARVIS Helm
chart, branches, and values files are configured externally in each cluster and
are not stored in this repository. The checked-in `argocd/argo-application.yaml`
manages Argo CD configuration from `main`; it is not the Application that deploys
the PA-JARVIS Helm release.

```text
feature branch -> dev -> dev-deployment -> dev -> main
                    |                         |
                    |                         `-> production Argo CD sync
                    `-> build images             using values-prd.yaml
                         |
                         `-> development Argo CD sync
                             using values-dev.yaml
```

### DEV deployment

1. Merge a feature branch into `dev` through a pull request.
2. A push to `dev` triggers `.github/workflows/build-images.yaml`. The workflow
   builds the Frontend, Backend, Agents, LLM, Tools, Storage, Scripts, and
   Analytics images from their service Dockerfiles and pushes them to GitHub
   Container Registry (GHCR).
3. Every image is tagged with the source commit SHA in the form
   `sha-<full-git-sha>`. This gives all eight services an immutable, traceable
   version for that build.
4. The reusable `.github/workflows/create-deployments.yaml` workflow writes the
   new tag to the image entries in the Helm environment files:
   `values-dev.yaml` and `values-prd.yaml`. It then publishes the changes to the
   generated deployment branches.
5. Review and merge `dev-deployment` into `dev`. The Helm-only change does not
   rebuild the images because the build workflow ignores changes beneath the
   Helm directory.
6. Argo CD detects the updated `values-dev.yaml` on `dev` and automatically
   synchronizes the Helm release to the development Kubernetes cluster.

### PROD deployment

1. Validate the SHA-tagged release in the development environment.
2. Promote the release by merging `dev` into `main` through a pull request.
3. The merge carries the approved image tags into `values-prd.yaml` on `main`.
4. Production Argo CD detects the Git change and synchronizes the Helm release
   to the production Kubernetes cluster.

The build workflow currently generates both `dev-deployment` and
`prd-deployment`, and updates both Helm values files on each generated branch.
The promotion controls remain the pull-request merges into `dev` and `main`.

### Kubernetes runtime configuration and secrets

Application images contain no environment-specific credentials. The Helm values
files select image repositories, immutable tags, replica settings, hosts, and
other non-secret deployment configuration. Credentials are stored separately as
Kubernetes Secrets in each target cluster and namespace before Argo CD deploys
the workloads.

The Helm deployment templates expect these Secret objects:

| Kubernetes Secret | Environment variables (Secret keys) | Used by |
| --- | --- | --- |
| `storage-db-secrets` | `PGSQL_HOSTNAME`, `PGSQL_PORT`, `PGSQL_USER`, `PGSQL_PASSWORD`, `PGSQL_DBNAME` | Storage, LLM, Tools, Scripts, Analytics |
| `llm-secrets` | `PRIMARY_PROVIDER`, `SECONDARY_PROVIDER`, `DEFAULT_PROVIDER`, plus credentials and model settings for the configured providers | Agents, LLM |
| `google-oauth-secrets` | `AK_GOOGLE_CLIENT_ID`, `AK_GOOGLE_CLIENT_SECRET`, `AK_GOOGLE_REFRESH_TOKEN` | Tools, Scripts |

The provider order variables in `llm-secrets` must contain supported provider
names: `gemini`, `groq`, or `qwen`. Include the variables required by each
provider selected in that order:

| Provider | Required variables | Optional variables |
| --- | --- | --- |
| Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` |
| Groq | `GROQ_API_KEY` | `GROQ_MODEL`, `GROQ_TIMEOUT_SECONDS` |
| Ollama/Qwen | None beyond a reachable Ollama service | `OLLAMA_MODEL`, `OLLAMA_HEALTH_TIMEOUT_SECONDS`, `OLLAMA_TIMEOUT_SECONDS` |

`OLLAMA_HOST` is currently set directly in `llm-deployment.yaml`, rather than
loaded from a Secret. `PGSQL_PORT` defaults to `5432`; database pool and timeout
settings are optional. Google Drive features additionally use
`AK_GDRIVE_ROOT_FOLDER_ID` and `AK_PICS_GDRIVE_ROOT_FOLDER_ID`. The current
Scripts template supplies `GDRIVE_ROOT_FOLDER_ID` and
`AK_GDRIVE_ROOT_FOLDER_ID` directly as deployment environment values.

The templates use two injection patterns:

- `envFrom.secretRef` exposes every key in a Secret as an environment variable.
  This is how the database, provider, and Google OAuth variables are loaded by
  most services.
- `env.valueFrom.secretKeyRef` maps one named key to one environment variable.
  The Agents template uses this pattern for `PRIMARY_PROVIDER`,
  `SECONDARY_PROVIDER`, and `DEFAULT_PROVIDER` from `llm-secrets`.

The referenced Secrets are not created by this Helm chart and must already
exist in the namespace where PA-JARVIS is installed. Maintain distinct Secret
objects and credentials for development and production. Do not commit Secret
manifests containing values, plaintext credentials, exported Secret YAML, or
local environment files to Git.

The Tools service's internet-search implementation also reads `GEMINI_API_KEY`
and `GEMINI_MODEL`. Its current Helm template does not reference `llm-secrets`,
so that Secret reference must be added to `tools-deployment.yaml` before the
internet-search tool can use Gemini in Kubernetes.

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
- Store production credentials in Kubernetes Secrets, restrict access with RBAC,
  enable encryption at rest, and never commit secret values to the repository.
- Review exposed ports and network access before deploying outside a trusted
  development environment.

## License

PA-JARVIS is licensed under the [MIT License](LICENSE).
