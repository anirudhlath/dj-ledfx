# dj-ledfx Monitoring

Real-time performance monitoring with Prometheus and Grafana.

## Quick Start

```bash
# One-time setup (macOS)
./scripts/setup-monitoring.sh

# Start Prometheus (suppress verbose logging)
prometheus --config.file=monitoring/prometheus.yml --log.level=warn &>/dev/null &

# Start Grafana
brew services start grafana

# Start dj-ledfx with metrics
uv run -m dj_ledfx --metrics --demo
```

### Grafana Setup

1. Open http://localhost:3000 (default credentials: admin / admin)
2. **Add Prometheus datasource:** Connections → Data sources → Add data source → Prometheus, set URL to `http://localhost:9090`, click Save & test
3. **Import dashboard:** Dashboards → Import → Upload JSON file, select `monitoring/grafana-dashboard.json`

> **Note:** Device discovery takes ~15s (Govee 5s + LIFX 10s). Dashboard panels will populate after discovery completes and Prometheus scrapes a few times.

## Ports

| Service | Port |
|---------|------|
| App metrics | :9091 |
| Prometheus | :9090 |
| Grafana | :3000 |

## Port Conflicts

If port 9091 is already in use by another process:

```bash
# Check what's using the port
lsof -i :9091 -P

# Use a different port
uv run -m dj_ledfx --metrics --metrics-port 19091 --demo
```

Then update `prometheus.yml` targets to match:

```yaml
      - targets: ["localhost:19091"]
```

And restart Prometheus: `pkill prometheus && prometheus --config.file=monitoring/prometheus.yml --log.level=warn &>/dev/null &`

## Stopping

```bash
brew services stop grafana
pkill prometheus
```

## Metrics Reference

See `src/dj_ledfx/metrics.py` for all metric definitions.
