# 01 — Setup: Isaac Lab Docker, WebRTC, MCP

This guide sets up the environment for **training** (Isaac Lab Docker) and **deploying** the walking policy (Isaac Sim with MCP extension, optionally WebRTC for viewing).

---

## Prerequisites

- Docker, Docker Compose, [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)
- (Optional) NGC account for pulling `nvcr.io/nvidia/isaac-sim` base image
- Isaac Lab repo and **isaac-sim-mcp** repo (MCP extension) on the host

---

## 1. Isaac Lab Docker + MCP extension

Clone Isaac Lab and ensure the MCP extension is available for the container:

```bash
cd /home/ubuntu   # or your workspace root
git clone https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab
./docker/ensure_mcp_extension.sh
python docker/container.py start
```

- **ensure_mcp_extension.sh** looks for `isaac-sim-mcp/isaac.sim.mcp_extension` next to IsaacLab (e.g. `~/isaac-sim-mcp`). It configures the compose mount so the extension is available at `/workspace/isaaclab/exts/isaac.sim.mcp_extension` inside the container.
- After changing compose volumes, run `python docker/container.py stop` then `python docker/container.py start` so the new container is created with the updated mounts.

---

## 2. WebRTC ports (optional — for viewing Sim in browser)

The Isaac Lab `docker-compose.yaml` already publishes:

- **8211** (TCP) — WebRTC client
- **49100** (TCP) — Livestream
- **47998** (UDP) — Livestream media

On your cloud host, open these ports in the firewall. Then, from inside the container:

```bash
python docker/container.py enter
cd /workspace/isaaclab
export PUBLIC_IP=$(curl -s ifconfig.me)
isaaclab -p scripts/tutorials/00_sim/launch_app.py --livestream 1 \
  --kit_args "--ext-folder /workspace/isaaclab/exts --enable isaac.sim.mcp_extension --/app/livestream/publicEndpointAddress=$PUBLIC_IP --/app/livestream/port=49100"
```

Connect from your machine: `http://<PUBLIC_IP>:8211/streaming/webrtc-client?server=<PUBLIC_IP>`.

**Note:** Livestream needs NVENC (e.g. T4). Not supported on A100.

---

## 3. Isaac Sim for MCP policy walk (separate from Isaac Lab)

Policy **deployment** (create scene, robot, run policy) uses **stock Isaac Sim** with the MCP extension, not the Isaac Lab container. Typical flow:

- Start Isaac Sim with the MCP extension (e.g. `run_isaac_sim_with_mcp.sh` on the host), which mounts the workspace and the exported policy volume.
- Cursor (or any MCP client) connects to the MCP server, which talks to the extension inside Isaac Sim.

Ensure:

- **isaac-sim-mcp** is at e.g. `~/isaac-sim-mcp` and the extension is loaded by Isaac Sim (`--ext-folder` / `--enable isaac.sim.mcp_extension`).
- Port **8766** is open if Cursor runs on another machine (MCP server listens there).

---

## 4. Connect Cursor to MCP

**Cursor on the same host as Isaac Sim:**

In `~/.cursor/mcp.json` (or project MCP settings):

```json
{
  "mcpServers": {
    "isaac-sim": {
      "command": "python3",
      "args": ["/home/ubuntu/isaac-sim-mcp/isaac_mcp/server.py"],
      "env": {}
    }
  }
}
```

Install MCP if needed: `pip install mcp`. Restart Cursor or reload MCP after changing the config.

**Cursor on a different machine (e.g. laptop):** Run the MCP server over SSH (command: `ssh`, args: `ubuntu@<BREV_IP>` `python3` `/home/ubuntu/isaac-sim-mcp/isaac_mcp/server.py`). Open TCP **8766** on the cloud firewall.

---

## 5. Restarting Isaac Sim (for policy walk)

If Isaac Sim hangs or you need a clean state:

```bash
docker restart isaac-sim
```

Or stop and start:

```bash
docker stop isaac-sim
docker start isaac-sim
```

Wait until Sim is fully up (e.g. 30–60 s), then reconnect via WebRTC (if used) and MCP. After restart, run: create physics scene → create robot (g1_minimal) → start_g1_policy_walk with your exported JIT policy.

---

## 6. Troubleshooting

- **MCP extension not visible in Isaac Lab container:** Recreate the container (`container.py stop` then `start`). Verify: `ls -la /workspace/isaaclab/exts/isaac.sim.mcp_extension/` inside the container.
- **Resolve volumes (host):** `cd ~/IsaacLab/docker && docker compose --env-file .env.base --profile base config` and check `services.isaac-lab-base.volumes` for the MCP extension bind.
