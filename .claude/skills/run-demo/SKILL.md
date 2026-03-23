---
name: run-demo
description: Start the app in demo mode with web UI for manual testing
disable-model-invocation: true
---

Start the dj-ledfx app in demo mode with the web UI enabled.

```bash
uv run -m dj_ledfx --demo --web
```

The web UI will be available at http://localhost:8080. Effects start in STOPPED state — use the Play button or press Space to start.
