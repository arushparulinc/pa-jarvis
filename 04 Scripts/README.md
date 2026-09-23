# Scripts service

Python service for PA Jarvis scheduled and utility scripts. Script modules live under `app/media`, `app/misc`, and `app/reminder`. Schedules are loaded from `config.script_schedules` in PostgreSQL when the service starts. Set `SCRIPTS_TIME_ZONE` to an IANA timezone if the default `America/Toronto` is not appropriate.

Each row identifies a script by `sched_type` (`media`, `misc`, or `reminder`/`reminders`) and `sched_name` (`pics`, `videos`, `quotes`, `events`, `shopping`, or `tasks`). `sched_day_of_week` accepts `*` for every day, `mon` for Mondays, or `mon,wed,fri` for selected days. `sched_hour` and `sched_minute` set the local run time. Only rows present at startup are scheduled; restart the service after changing the table. Unknown names, duplicate entries, and incomplete times prevent startup. The script `run()` functions are still placeholders. Keep one service process/replica unless you add a shared job store or leader election.

Run locally from this directory with `uv sync --frozen` and `uv run uvicorn app.main:app --host 0.0.0.0 --port 8005`. The `GET /health` endpoint reports service availability.
