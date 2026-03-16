# WebRTC access to Isaac Sim Docker instance

This note describes how WebRTC livestream is configured when you start Isaac Sim with `run_isaac_sim_with_mcp.sh` and how to check that it is reachable.

---

## Script validation (run_isaac_sim_with_mcp.sh)

The launcher is set up as follows; use this to validate Docker and access:

| Item | Setup | How to verify |
|------|--------|----------------|
| **Network** | `--network=host` | Container uses host network; no port mapping, so `docker ps` shows PORTS empty. MCP and WebRTC bind directly on the host. |
| **MCP** | Extension on port **8766**, host 0.0.0.0 | From host: connect to `localhost:8766`. Remote: use `<host-ip>:8766` and open TCP 8766 in firewall/SG. |
| **WebRTC** | Livestream port 49100, HTTP on **8211** (set in start script), public IP from `curl ifconfig.me` | Ports on host: **8211** (HTTP client), **49100** (TCP), **47998** (UDP). Open these for remote browser. |
| **sim_worlds** | `~/sim_worlds` → `/home/sim_worlds` (rw) | Container user 1234 must read; run `chmod -R a+rX ~/sim_worlds` on host if needed. |
| **GPU** | `--gpus all` | Required for Isaac Sim. |

If you change to a non-host network, add explicit port publishing: `-p 8766:8766 -p 8211:8211 -p 49100:49100 -p 47998:47998/udp`.

---

## Current setup

**Host launcher** ([run_isaac_sim_with_mcp.sh](../scripts/run_isaac_sim_with_mcp.sh)):

- Runs the container with **`--network=host`**, so the container shares the host network. Any port Isaac Sim listens on is directly on the host (no `-p` mapping needed).

**Container entrypoint** ([start_isaac_with_mcp.sh](../scripts/start_isaac_with_mcp.sh)):

- Starts Isaac Sim with `runheadless.sh` and passes:
  - `--/exts/omni.services.transport.server.http/port=8211` (HTTP server for WebRTC client page)
  - `--/app/livestream/publicEndpointAddress=$PUBLIC_IP` (public IP from `curl ifconfig.me`)
  - `--/app/livestream/port=49100`

So the WebRTC client page is served on **port 8211**, livestream on **49100**, and the host’s public IP is advertised for remote connections.

---

## Ports used by WebRTC / livestream

| Port    | Protocol | Purpose                          |
|---------|----------|-----------------------------------|
| **8211**  | TCP      | HTTP server for the WebRTC client (browser page) |
| **49100** | TCP      | Livestream / WebRTC signaling (set in start script) |
| **47998** | UDP      | Livestream media (often needed for WebRTC)        |

The start script forces the HTTP server to **8211** via `--/exts/omni.services.transport.server.http/port=8211` so it matches typical firewall/security group rules (e.g. Brev/EC2). With `--network=host`, these are the **host** ports. From another machine you use the **host’s IP** (or public IP in the cloud).

---

## How to check WebRTC access

### 1. Start Isaac Sim with MCP

```bash
./workspace/scripts/run_isaac_sim_with_mcp.sh
```

Wait until the app is ready (e.g. log line like “Isaac Sim Full Streaming App is loaded” or “app ready”).

### 2. Check from the host

On the same machine that runs Docker:

```bash
# Verify 200 (server is up)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8211/health
# Probe all paths: ./workspace/scripts/probe_webrtc_http.sh
# Ports: ss -tlnp | grep -E '8211|8011|49100'
```

Only `/health` and `/status` return 200; `/streaming/webrtc-client` returns 404. Use the **desktop** WebRTC Streaming Client (AppImage) to view the stream (step 3).

### 3. View the stream (desktop client)

No browser client is served (`/streaming/webrtc-client` returns 404). Use the **desktop** app: (1) Download [Isaac Sim WebRTC Streaming Client](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html#isaac-sim-latest-release) (AppImage on Linux). (2) Run the client; set server to host IP (or `127.0.0.1` if local). Signaling: **port 49100**. (3) Open **TCP 49100** and **UDP 47998** on the host/firewall for remote access.  

### 4. Firewall / security group

For remote access, the host (or cloud security group) must allow:

- **TCP 8211** (optional; HTTP /health, /status only)
- **TCP 49100** (livestream signaling — required for desktop client)
- **UDP 47998** (livestream media)

Example (host firewall, if you use it):

```bash
sudo ufw allow 8211/tcp
sudo ufw allow 49100/tcp
sudo ufw allow 47998/udp
sudo ufw reload
```

In AWS/Brev, add inbound rules for these ports (and restrict by your IP if desired).

---

## If you don’t use `--network=host`

If you change the launcher to a normal bridge network (no `--network=host`), publish the same ports so the host can reach the container:

```bash
docker run ... \
  -p 8211:8211 \
  -p 49100:49100 \
  -p 47998:47998/udp \
  ...
```

Then use **host IP** and **8211** with path `/streaming/webrtc-client?server=<host-ip>` (root `/` returns 404).

---

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| **HTTP 404** on `/streaming/webrtc-client` | This app does not serve a browser client. Use the **desktop** Isaac Sim WebRTC Streaming Client (AppImage); connect to host IP, port 49100. |
| Connection refused or ERR_EMPTY_RESPONSE on 8211 | Ensure the start script passes `--/exts/omni.services.transport.server.http/port=8211`. Check logs for "Server will attempt to start on http://0.0.0.0:8211". |
| Connection refused on 8211 | Isaac Sim may not have started the HTTP server; check logs for `omni.services.transport.server.http` and "Server will attempt to start". |
| Page loads but no stream | Ensure 49100 and 47998 are open and that `publicEndpointAddress` matches the IP you use to reach the host (e.g. public IP for internet access). |
| Only works on localhost | Firewall or security group is likely blocking 8211/49100/47998 from outside. |

Reference: [Isaac Sim – Livestream Clients](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html).
