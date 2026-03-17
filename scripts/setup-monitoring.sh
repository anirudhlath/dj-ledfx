#!/usr/bin/env bash
set -euo pipefail

echo "=== dj-ledfx Monitoring Setup ==="

# Platform detection
if [[ "$(uname)" != "Darwin" ]]; then
    echo ""
    echo "This script supports macOS (brew) only."
    echo ""
    echo "For Linux, install manually:"
    echo "  Prometheus: https://prometheus.io/download/"
    echo "  Grafana:    https://grafana.com/grafana/download?platform=linux"
    echo ""
    echo "Then use the config files in monitoring/ directory."
    exit 1
fi

# Check for brew
if ! command -v brew &> /dev/null; then
    echo "ERROR: Homebrew not found. Install from https://brew.sh"
    exit 1
fi

# Install Prometheus
if ! command -v prometheus &> /dev/null; then
    echo "Installing Prometheus..."
    brew install prometheus
else
    echo "Prometheus already installed: $(prometheus --version 2>&1 | head -1)"
fi

# Install Grafana
if ! brew list grafana &> /dev/null 2>&1; then
    echo "Installing Grafana..."
    brew install grafana
else
    echo "Grafana already installed"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the monitoring stack:"
echo ""
echo "  1. Start Prometheus (port 9090):"
echo "     prometheus --config.file=monitoring/prometheus.yml --log.level=warn &>/dev/null &"
echo ""
echo "  2. Start Grafana (port 3000):"
echo "     brew services start grafana"
echo ""
echo "  3. Start dj-ledfx with metrics (port 9091):"
echo "     uv run -m dj_ledfx --metrics --demo"
echo "     (If port 9091 is taken: --metrics-port 19091, then update prometheus.yml)"
echo ""
echo "  4. Open Grafana at http://localhost:3000 (admin/admin)"
echo "     - Add Prometheus datasource: Connections → Data sources → Prometheus"
echo "       Set URL to http://localhost:9090, click Save & test"
echo "     - Import dashboard: Dashboards → Import → Upload grafana-dashboard.json"
echo ""
echo "  Note: Device discovery takes ~15s. Dashboard populates after that."
echo ""
echo "To stop:"
echo "  brew services stop grafana"
echo "  pkill prometheus"
