# Gemini integration

This package contains the Gemini adapter used by the FastAPI backend.

Copy `.env.example` to `.env`, add a Google AI Studio API key, and start the
backend from `02 Source/Backend/fastpy_backend`. The backend loads that file at
startup. `GEMINI_MODEL` is optional and defaults to `gemini-2.5-flash`.
