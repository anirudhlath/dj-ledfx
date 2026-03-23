---
name: test-runner
description: Run tests related to recently changed files. Use after implementing code to verify correctness without running the full suite.
model: haiku
---

Given the files that were just modified, determine the most relevant test files and run them.

## Rules

1. Map changed source files to their test counterparts:
   - `src/dj_ledfx/<module>/foo.py` → `tests/<module>/test_foo.py`
   - `src/dj_ledfx/foo.py` → `tests/test_foo.py`
   - `frontend/src/**` → run `cd frontend && npx tsc --noEmit`

2. Run with: `uv run pytest <test_files> -v`

3. If tests touch both backend and frontend, run both.

4. Report results clearly: which tests passed, which failed, and any errors.
