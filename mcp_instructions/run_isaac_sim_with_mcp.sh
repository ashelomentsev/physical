#!/bin/bash
# Start Isaac Sim with MCP extension enabled (runs Docker and executes start_isaac_with_mcp.sh inside the container).
# Run from host. Policy should be in volume g1-exported-policy (see workspace/scripts/archive/export_g1_policy_into_volume.sh).
# Inside the container: workspace at /home/workspace, exported policy at /home/workspace/exported.
#
# Docker and access validation:
#   - --network=host: container shares host network; no -p port mapping is used, so "docker ps" shows PORTS empty.
#     Services (MCP 8766, WebRTC 8211, livestream 49100/47998) bind directly on the host and are reachable as localhost:<port>.
#   - MCP: extension listens on 8766 (config: isaac.sim.mcp server.host=0.0.0.0, server.socket=8766).
#     Connect from host as localhost:8766; from another machine use <host-ip>:8766 (open TCP 8766 in firewall/SG).
#   - WebRTC: HTTP client on 8211 (set in start script), livestream 49100 (TCP), 47998 (UDP). Open these for remote browser access.
#   - sim_worlds: mounted rw at /home/sim_worlds; ensure host dir is readable by container user (chmod -R a+rX ~/sim_worlds).
# See workspace/docs/ISAAC_SIM_WEBRTC_ACCESS.md for WebRTC checks and firewall.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Paths on host (adjust if your layout differs)
ISAAC_MCP_EXT="${ISAAC_MCP_EXT:-$HOME/isaac-sim-mcp}"
DOCKER_CACHE="${DOCKER_CACHE:-$HOME/docker/isaac-sim}"

if [ ! -d "$ISAAC_MCP_EXT/isaac.sim.mcp_extension" ]; then
  echo "MCP extension not found at $ISAAC_MCP_EXT/isaac.sim.mcp_extension. Set ISAAC_MCP_EXT or clone isaac-sim-mcp." >&2
  exit 1
fi

# Mount the container-entry script from workspace so it works after refactor
START_SCRIPT="$SCRIPT_DIR/start_isaac_with_mcp.sh"
if [ ! -f "$START_SCRIPT" ]; then
  echo "Start script not found: $START_SCRIPT" >&2
  exit 1
fi

# SSH tunnel mode: LIVESTREAM_PUBLIC_IP=127.0.0.1 TUNNEL_MODE=1 ./run_isaac_sim_with_mcp.sh
# TUNNEL_MODE=1 starts a socat relay that bridges UDP 47998 (WebRTC media) over TCP port 47999,
# which is then forwarded through the SSH tunnel by ssh_tunnel_mac.sh.
# X11 forwarding: set DISPLAY before running (done automatically when using ssh_tunnel_mac.sh).
# When DISPLAY is set, xauth cookie is shared with the container for GUI app access.
if [ "${TUNNEL_MODE:-0}" = "1" ]; then
  if ! command -v socat &>/dev/null; then
    echo "TUNNEL_MODE=1 requires socat. Installing..." >&2
    sudo apt-get install -y socat >&2
  fi
  pkill -f "socat TCP-LISTEN:47999" 2>/dev/null || true
  socat TCP-LISTEN:47999,fork,reuseaddr UDP:127.0.0.1:47998 &
  SOCAT_SERVER_PID=$!
  echo "socat UDP relay started (PID $SOCAT_SERVER_PID): TCP :47999 -> UDP :47998"
fi
DISPLAY_OPTS=()
if [ -n "${DISPLAY:-}" ]; then
  XAUTH_TMP=$(mktemp /tmp/isaac-xauth-XXXXX)
  xauth nlist "$DISPLAY" 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f "$XAUTH_TMP" nmerge - 2>/dev/null || true
  chmod 644 "$XAUTH_TMP"
  DISPLAY_OPTS=(-e "DISPLAY=$DISPLAY" -e "XAUTHORITY=/tmp/.isaac-xauth" -v "$XAUTH_TMP:/tmp/.isaac-xauth:ro")
  echo "X11 forwarding enabled (DISPLAY=$DISPLAY)"
fi

# Use default HTTP port 8011 (no 8211 override): USE_DEFAULT_HTTP_PORT=1 ./workspace/scripts/run_isaac_sim_with_mcp.sh
docker run --name isaac-sim --entrypoint bash -it --gpus all -e "ACCEPT_EULA=Y" --rm --network=host \
  -e "PRIVACY_CONSENT=Y" \
  -e "USE_DEFAULT_HTTP_PORT=${USE_DEFAULT_HTTP_PORT:-0}" \
  -e "LIVESTREAM_PUBLIC_IP=${LIVESTREAM_PUBLIC_IP:-}" \
  "${DISPLAY_OPTS[@]}" \
  -v "${DOCKER_CACHE}/cache/main:/isaac-sim/.cache:rw" \
  -v "${DOCKER_CACHE}/cache/computecache:/isaac-sim/.nv/ComputeCache:rw" \
  -v "${DOCKER_CACHE}/logs:/isaac-sim/.nvidia-omniverse/logs:rw" \
  -v "${DOCKER_CACHE}/config:/isaac-sim/.nvidia-omniverse/config:rw" \
  -v "${DOCKER_CACHE}/data:/isaac-sim/.local/share/ov/data:rw" \
  -v "${DOCKER_CACHE}/pkg:/isaac-sim/.local/share/ov/pkg:rw" \
  -v "$ISAAC_MCP_EXT/isaac.sim.mcp_extension:/isaac-sim/exts/isaac.sim.mcp_extension:ro" \
  -v "$START_SCRIPT:/isaac-sim/start_isaac_with_mcp.sh:ro" \
  -v "$WORKSPACE_ROOT:/home/workspace:rw" \
  -v g1-exported-policy:/home/workspace/exported:rw \
  -v "${HOME}/training_results:/home/workspace/training_results:ro" \
  -v "${HOME}/sim_worlds:/home/sim_worlds" \
  -u 1234:1234 \
  nvcr.io/nvidia/isaac-sim:5.1.0 \
  /isaac-sim/start_isaac_with_mcp.sh
