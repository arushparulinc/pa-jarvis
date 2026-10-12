"""Tests for Scripts-service execution logging."""

import unittest
from unittest.mock import AsyncMock, patch

from app.call_storage import log_script_execution


class ScriptExecutionLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logs_script_provided_success_values(self):
        @log_script_execution(
            "example.script",
            success_event_name="Work finished",
            success_event_type="Success",
            failure_event_type="Failed",
        )
        async def run():
            return "result"

        with patch("app.call_storage.log_script_event", new=AsyncMock()) as log_event:
            result = await run()

        self.assertEqual(result, "result")
        log_event.assert_awaited_once_with(
            event_name="Work finished",
            event_type="Success",
            script_name="example.script",
        )

    async def test_logs_exception_message_and_reraises(self):
        @log_script_execution(
            "example.script",
            success_event_name="Work finished",
            success_event_type="Success",
            failure_event_type="Failed",
        )
        async def run():
            raise ValueError("download failed")

        with patch("app.call_storage.log_script_event", new=AsyncMock()) as log_event:
            with self.assertRaisesRegex(ValueError, "download failed"):
                await run()

        log_event.assert_awaited_once_with(
            event_name="download failed",
            event_type="Failed",
            script_name="example.script",
        )


if __name__ == "__main__":
    unittest.main()
