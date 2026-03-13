# dj-ledfx Monitoring

Real-time performance monitoring with Prometheus and Grafana.

## Quick Start

```bash
# One-time setup (macOS)
./scripts/setup-monitoring.sh

# Start the stack
prometheus --config.file=monitoring/prometheus.yml &
brew services start grafana
uv run -m dj_ledfx --metrics --demo

# Open Grafana
open http://localhost:3000
# Default credentials: admin / admin
# Import monitoring/grafana-dashboard.json
```

## Ports

| Service | Port |
|---------|------|
| App metrics | :9091 |
| Prometheus | :9090 |
| Grafana | :3000 |

## Custom Metrics Port

```bash
uv run -m dj_ledfx --metrics --metrics-port 8080
```

Update `prometheus.yml` targets accordingly.

## Metrics Reference

See `src/dj_ledfx/metrics.py` for all metric definitions.
