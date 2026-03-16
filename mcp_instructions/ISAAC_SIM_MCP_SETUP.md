# Isaac Sim Official MCP Server Setup

## Current Status
- ✅ Official Isaac Sim MCP repository cloned to `/home/ubuntu/isaac-sim-mcp`
- ✅ MCP dependencies installed (`mcp[cli]`)
- ✅ Extension copied to Isaac Sim container
- ⚠️ Extension needs to be enabled in Isaac Sim
- ⚠️ Cursor config updated to use official server

## Required Steps

### 1. Enable the MCP Extension in Isaac Sim

The extension needs to be enabled when starting Isaac Sim. You have two options:

#### Option A: Restart Isaac Sim with Extension Enabled

Update your `run_isaac_sim.sh` to include the extension folder and enable it:

```bash
docker run --name isaac-sim --entrypoint bash -it --gpus all -e "ACCEPT_EULA=Y" --rm --network=host \
	-e "PRIVACY_CONSENT=Y" \
	-v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
	-v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
	-v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
	-v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
	-v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
	-v ~/docker/isaac-sim/pkg:/isaac-sim/.local/share/ov/pkg:rw \
	-v /home/ubuntu/isaac-sim-mcp:/isaac-sim/exts/isaac-sim-mcp:ro \
	-u 1234:1234 \
	nvcr.io/nvidia/isaac-sim:5.1.0 \
	--ext-folder /isaac-sim/exts/isaac-sim-mcp --enable isaac.sim.mcp_extension
```

#### Option B: Enable Extension in Running Container

If Isaac Sim is already running, you may need to restart it with the extension enabled. The extension will start a server on `localhost:8766`.

### 2. Verify Extension is Running

After starting Isaac Sim with the extension enabled, check that the server is listening:

```bash
docker exec isaac-sim netstat -tlnp 2>/dev/null | grep 8766
```

You should see output like:
```
tcp        0      0 127.0.0.1:8766          0.0.0.0:*               LISTEN
```

### 3. Update Cursor Configuration

The Cursor configuration has been updated to use the official server. The config file at `/home/ubuntu/cursor_mcp_config.json` now points to:

```json
{
  "mcpServers": {
    "isaac-sim": {
      "command": "ssh",
      "args": [
        "ubuntu@13.217.35.13",
        "python3",
        "/home/ubuntu/isaac-sim-mcp/isaac_mcp/server.py"
      ],
      "env": {}
    }
  }
}
```

Copy this configuration to your Cursor settings:
- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/mcp.json`
- **Windows**: `%APPDATA%\Cursor\User\globalStorage\mcp.json`
- **Linux**: `~/.config/Cursor/User/globalStorage/mcp.json`

### 4. Test the Connection

Test the MCP server manually:

```bash
python3 /home/ubuntu/isaac-sim-mcp/isaac_mcp/server.py
```

Or test with MCP inspector:
```bash
python3 -m mcp dev /home/ubuntu/isaac-sim-mcp/isaac_mcp/server.py
```

## Troubleshooting

### Extension Not Starting
- Check Isaac Sim logs: `docker logs isaac-sim | grep -i mcp`
- Verify extension is in the correct location: `docker exec isaac-sim ls -la /isaac-sim/exts/isaac.sim.mcp_extension`
- Ensure Isaac Sim version is 4.2.0 or higher

### Port 8766 Not Listening
- The extension must be enabled when Isaac Sim starts
- Check if the extension loaded: Look for "Isaac Sim MCP server started on localhost:8766" in logs
- Verify network settings allow localhost connections

### MCP Server Connection Errors
- Ensure the extension is running (port 8766 listening)
- Check that the server script can connect to localhost:8766
- Verify SSH connection from Cursor to the server works

## Available MCP Tools

Once connected, you'll have access to these tools:
- `get_scene_info` - Check connection and scene status
- `create_physics_scene` - Create physics environment
- `create_robot` - Add robots (franka, jetbot, carter, g1, go1)
- `omni_kit_command` - Execute Omni Kit commands
- `execute_script` - Run Python code in Isaac Sim
- `generate_3d_from_text_or_image` - Generate 3D models
- `search_3d_usd_by_text` - Search USD assets
- `transform` - Transform objects in the scene
