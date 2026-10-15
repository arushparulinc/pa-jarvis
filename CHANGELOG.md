# Changelog

All notable changes to PA-JARVIS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Root `.gitignore` and `CHANGELOG.md`.
- `LICENSE` (MIT).
- `.github/workflows/ci.yml` — structure validation and placeholder backend/frontend jobs.

### Planned

- Dark mode for the TV display.
- Dynamic internet-sourced quotes for the TV display.
- Internet integration for PA-JARVIS weather information.

## [0.3.0] - 2026-10-14

### Added

- Deployed the PA-JARVIS MVP with eight services:
  - Frontend — port `5173`
  - Backend — port `8000`
  - Agents — port `8001`
  - LLM — port `8002`
  - Tools — port `8003`
  - Storage — port `8004`
  - Scripts — port `8005`
  - Analytics dashboard — port `8006`

## [0.2.0] - 2026-09-24

### Added

- Analytics service for serving the dashboard and TV displays.

## [0.1.0] - 2026-07-05

### Added

- Initial numbered repository folder structure:
  - `01 Documents` — business, product, project management, architecture, engineering, operations, portfolio
  - `02 Source` — backend, frontend, agent, tools, MCP server, shared
  - `03 Infrastructure` — docker, kubernetes, nginx, terraform, ansible
  - `04 Scripts`
  - `05 Tests` — unit, integration, e2e
  - `06 Assets` — images, icons, diagrams
- `AGENTS.md` — Repository agent instructions.
- `README.md` — project milestones and overview.
