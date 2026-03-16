#!/bin/bash
# Script to run INSIDE the Isaac Sim Docker container to start Isaac Sim with MCP extension.
# Do not run this directly on the host. Use the launcher from the host instead:
#   ./workspace/scripts/run_isaac_sim_with_mcp.sh
# (from repo root) or: ./run_isaac_sim_with_mcp.sh (from workspace/scripts).

if [ ! -d /isaac-sim ] || [ ! -f /isaac-sim/runheadless.sh ]; then
  echo "This script must run inside the Isaac Sim Docker container (paths /isaac-sim and runheadless.sh not found)." >&2
  echo "From the host, start Isaac Sim with MCP using:" >&2
  echo "  ./workspace/scripts/run_isaac_sim_with_mcp.sh" >&2
  exit 1
fi

cd /isaac-sim

# Public IP for WebRTC. Set LIVESTREAM_PUBLIC_IP=127.0.0.1 when using SSH tunnel.
PUBLIC_IP="${LIVESTREAM_PUBLIC_IP:-$(curl -s --connect-timeout 3 ifconfig.me 2>/dev/null || true)}"
LIVESTREAM_OPTS=(--/app/livestream/port=49100)
if [ -n "$PUBLIC_IP" ]; then
  LIVESTREAM_OPTS=(--/app/livestream/publicEndpointAddress="$PUBLIC_IP" --/app/livestream/port=49100)
else
  echo "Warning: could not get public IP (curl ifconfig.me failed); WebRTC may only work from this host."
fi

# HTTP server for WebRTC client page. Default 8211 to match firewall (Brev/EC2). Set USE_DEFAULT_HTTP_PORT=1 to use app default 8011 (for testing curl 200).
RUN_OPTS=(--ext-folder /isaac-sim/exts --enable isaac.sim.mcp_extension)
if [ "${USE_DEFAULT_HTTP_PORT:-0}" != "1" ]; then
  RUN_OPTS+=(--/exts/omni.services.transport.server.http/port=8211)
fi

./runheadless.sh \
  "${RUN_OPTS[@]}" \
  "${LIVESTREAM_OPTS[@]}"
