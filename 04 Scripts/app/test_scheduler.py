import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from .main import app
from .scheduler.schedule_store import load_schedules


SCHEDULE_ROWS = {
    "media": [
        {"sched_name": "pics", "sched_day_of_week": "mon", "sched_hour": 18, "sched_minute": 0},
        {"sched_name": "videos", "sched_day_of_week": "*", "sched_hour": 19, "sched_minute": 30},
    ],
    "reminder": [
        {"sched_name": name, "sched_day_of_week": "*", "sched_hour": 18, "sched_minute": 0}
        for name in ("events", "shopping", "tasks")
    ],
    "misc": [
        {"sched_name": "quotes", "sched_day_of_week": "fri", "sched_hour": 8, "sched_minute": 15},
    ],
}


class ScheduleStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_script(self):
        connection = AsyncMock()
        connection.fetch.return_value = [
            {"sched_name": "unknown", "sched_day_of_week": "*", "sched_hour": 18, "sched_minute": 0}
        ]
        with self.assertRaisesRegex(ValueError, "Unknown script schedule"):
            await load_schedules(connection, ["media"], {"pics": lambda: None})


class SchedulerStartupTests(unittest.TestCase):
    def test_registers_jobs_from_database_rows(self):
        connection = AsyncMock()

        async def fetch(_query, sched_types):
            return [row for sched_type in sched_types for row in SCHEDULE_ROWS.get(sched_type, [])]

        connection.fetch.side_effect = fetch
        with patch("app.main.asyncpg.connect", new=AsyncMock(return_value=connection)):
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                jobs = {job.id: str(job.trigger) for job in app.state.scheduler.get_jobs()}

        self.assertEqual(len(jobs), 6)
        self.assertIn("day_of_week='mon'", jobs["media_pics"])
        self.assertIn("hour='19'", jobs["media_videos"])
        self.assertIn("minute='30'", jobs["media_videos"])
        self.assertIn("day_of_week='fri'", jobs["misc_quotes"])
        connection.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
