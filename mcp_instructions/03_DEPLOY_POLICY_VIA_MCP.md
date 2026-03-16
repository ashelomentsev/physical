# 03 — Deploy Policy via MCP

This guide covers **exporting** an Isaac Lab RSL-RL checkpoint to a JIT policy (`.pt`) and **running** it in Isaac Sim via MCP so the G1 robot walks on a flat surface.

---

## Prerequisites

- A trained checkpoint from Isaac Lab (e.g. `model_4498.pt` in `logs/rsl_rl/g1_flat/<run>/`).
- Isaac Sim running with the MCP extension (see [01_SETUP.md](01_SETUP.md)).
- Cursor (or another MCP client) connected to the MCP server.

---

## 1. Export RSL-RL checkpoint to JIT

Isaac Lab checkpoints (`.pt`) contain the full training state. The MCP extension’s `start_g1_policy_walk` expects a **JIT-exported** policy (callable module, 123 → 37).

Use the workspace script:

```bash
# From the host (Python 3 + PyTorch required)
python workspace/scripts/export_policy.py \
  --checkpoint /path/to/model_4498.pt \
  --output workspace/exported/g1_flat_policy_4498.pt
```

Example if the checkpoint is in `training_results`:

```bash
python workspace/scripts/export_policy.py \
  --checkpoint ~/training_results/isaac_lab_rsl_rl/rsl_rl_resumed/g1_flat/2026-02-07_19-55-29/model_4498.pt \
  --output workspace/exported/g1_flat_policy_4498.pt
```

The script builds the actor network (123 → 256 → 128 → 128 → 37, ELU) from the checkpoint’s `model_state_dict` and saves it with `torch.jit.trace`.

---

## 2. Policy path for Isaac Sim (Docker)

If Isaac Sim runs via `run_isaac_sim_with_mcp.sh`, **`/home/workspace/exported` inside the container is the named volume `g1-exported-policy`**, not the host `workspace/exported`. The policy file must be **inside that volume** for the extension to load it.

- **Host path:** e.g. `~/workspace/exported/g1_nav_flat_policy_6500.pt`
- **Inside container:** `/home/workspace/exported/g1_nav_flat_policy_6500.pt` (same path; content comes from the volume).

Use the **container path** when calling MCP `start_g1_policy_walk` (e.g. `/home/workspace/exported/g1_nav_flat_policy_6500.pt`).

### Copy policy into the volume (required once)

**If Isaac Sim is already running:**

```bash
docker cp /home/ubuntu/workspace/exported/g1_nav_flat_policy_6500.pt isaac-sim:/home/workspace/exported/
docker exec isaac-sim chmod 644 /home/workspace/exported/g1_nav_flat_policy_6500.pt
```

**If Isaac Sim is stopped**, populate the volume then start Sim:

```bash
docker run --rm -v g1-exported-policy:/exported -v /home/ubuntu/workspace/exported:/from alpine sh -c "cp /from/g1_nav_flat_policy_6500.pt /exported/ && chmod 644 /exported/g1_nav_flat_policy_6500.pt"
./workspace/scripts/run_isaac_sim_with_mcp.sh
```

Then call `start_g1_policy_walk` with `policy_path="/home/workspace/exported/g1_nav_flat_policy_6500.pt"`.

### Policy from `training_results_nav` (best checkpoint)

If the policy lives under `training_results_nav/isaac_lab_rsl_rl/best_checkpoint/` on the host, copy it into the Sim container so the extension can load it:

```bash
# Replace CONTAINER_NAME with your Isaac Sim container (e.g. isaac-sim or isaac-lab-base)
docker cp /home/ubuntu/training_results_nav/isaac_lab_rsl_rl/best_checkpoint/model_1550_nav_flat_best.pt CONTAINER_NAME:/home/workspace/exported/
docker exec CONTAINER_NAME chmod 644 /home/workspace/exported/model_1550_nav_flat_best.pt
```

Then use `policy_path="/home/workspace/exported/model_1550_nav_flat_best.pt"` in MCP. Export to JIT first if needed (see README in best_checkpoint).

---

## 3. MCP-only workflow (create scene, robot, walk)

All steps are MCP tool calls. Order matters.

### 3.1 Verify connection

- **Tool:** `get_scene_info`
- **Expected:** `status: "success"`, `message: "pong"`

### 3.2 Create physics scene

- **Tool:** `create_physics_scene`
- **Arguments:** `floor: true`, `objects: []`, `gravity: [0, 0, -9.81]`

**Obstacles (wider gap so G1 can walk between):** Use `y = ±1.5` so the corridor is 3 m wide. Example:
```json
"objects": [
  {"type": "Cube", "name": "obstacle_left", "position": [2, 1.5, 0.5], "scale": [0.5, 0.5, 1], "color": [0.8, 0.2, 0.2, 1], "is_kinematic": true},
  {"type": "Cube", "name": "obstacle_right", "position": [2, -1.5, 0.5], "scale": [0.5, 0.5, 1], "color": [0.2, 0.2, 0.8, 1], "is_kinematic": true}
]
```
Tighter gaps (e.g. `y = ±0.8`) can cause the robot to clip or get stuck. To change obstacle positions you must create a **new** scene (restart Isaac Sim or create a fresh scene before creating the robot).

### 3.3 Create G1 robot (use g1_minimal)

- **Tool:** `create_robot`
- **Arguments:** `robot_type: "g1_minimal"`, `position: [0, 0, 0.74]`

Use **`g1_minimal`** for the Isaac Lab–trained flat policy. It has 37 DOFs and the same joint order as in training. Using `g1` (43 DOFs) would mismatch observation/action indices and cause wrong or unstable behavior.

### 3.4 Start policy walk

- **Tool:** `start_g1_policy_walk`
- **Arguments:**
  - `policy_path`: Container path to the JIT `.pt` (e.g. `/home/workspace/exported/g1_flat_policy_4498.pt`)
  - `robot_prim_path`: `"/G1"`
  - `target_velocity`: `0.5` (m/s)
  - `deterministic`: `true`

The extension loads the policy, resets the robot to the training default pose (0.74 m, default joint positions, zero velocities), and registers a callback that runs policy inference every frame and applies joint targets. The robot walks until you call `stop_g1_policy_walk`.

### 3.5 (Optional) Change target velocity

- **Tool:** `set_velocity_command`
- **Arguments:** `lin_vel_x`, `lin_vel_y`, `ang_vel_z` (clamped to training ranges)

### 3.6 Stop walking

- **Tool:** `stop_g1_policy_walk`

### 3.7 Point-to-point navigation (optional)

You can drive the robot to a target XY position and poll until arrival. Navigation runs as a non-blocking callback; the policy walk keeps running and is steered each physics step.

- **Tool:** `navigate_to`
  - **Arguments:**
    - `target_position`: `[x, y]` world coordinates in metres (required)
    - `robot_prim_path`: `"/G1"` (default)
    - `policy_path`: Path to JIT `.pt`. Required only if `start_g1_policy_walk` was not already called (otherwise navigation reuses the running policy)
    - `arrival_threshold`: Distance in metres to consider “arrived” (default `0.5`)

  Returns immediately. A PRE_UPDATE callback rotates the robot in place when |yaw_error| > 0.3 rad, then drives forward while correcting yaw; it unsubscribes itself on arrival.

- **Tool:** `get_navigation_status`  
  Returns `nav_status` (`idle` | `navigating` | `arrived` | `failed`), `target_position`, `current_position`, `distance_to_target`. Poll this until `nav_status == "arrived"` (or to cancel with `stop_navigation`).

- **Tool:** `stop_navigation`  
  Stops the navigation callback and zeroes velocity commands. The policy walk continues (robot remains balanced).

**Example flow:**

```
navigate_to(target_position=[5.0, 3.0], policy_path="/home/workspace/exported/g1_flat_policy_4498.pt")
start_simulation()
# Poll until arrived:
get_navigation_status()  →  { "nav_status": "navigating", "distance_to_target": 3.21 }
get_navigation_status()  →  { "nav_status": "arrived", "distance_to_target": 0.42 }
stop_g1_policy_walk()
stop_simulation()
```

---

## 4. Restarting Isaac Sim

After changing the extension or scene, restart Isaac Sim (e.g. `docker restart isaac-sim`). Then run again: `create_physics_scene` → `create_robot` (g1_minimal) → `start_g1_policy_walk`.

---

## 5. Policy vs robot (g1_minimal vs g1)

| Robot type   | DOFs | Use case |
|--------------|------|----------|
| **g1_minimal** | 37   | Isaac Lab flat velocity policy (same USD and joint order as training). |
| **g1**       | 43   | Full G1; do **not** use with the 37-DOF flat policy. |

The policy expects observations of size 123 and actions of size 37. The MCP extension builds observations (body-frame velocities, projected gravity, velocity commands, joint positions relative to default, joint velocities, last action) and applies actions as `default_pos + action * 0.5` (Isaac Lab scale). All of this is defined for **g1_minimal**; using **g1** would require a different policy or a name-based DOF mapping (see `docs/archive/G1_POLICY_ROBOT_MISMATCH_ANALYSIS.md`).

---

## 6. Troubleshooting: Robot falls or doesn’t walk

If the robot **moves its legs in a plausible way but still falls** (e.g. repeated `[FALL] step=… z=…m — resetting` in the Isaac Sim log), the cause is usually **dynamics/timing**, not joint mapping.

### Physics step rate (most likely)

Training uses **200 Hz physics** (`sim.dt=0.005`) and **50 Hz control** (policy every 4 steps). In Isaac Sim, if the physics step is different (e.g. default 60 Hz), the policy runs at 60/4 = **15 Hz**. The same leg motions then run at the wrong rate and the robot loses balance.

- **Fix:** Call **`create_physics_scene`** and **`start_simulation`** (or ensure the timeline is playing) before **`start_g1_policy_walk`**. The extension sets `physics_dt=0.005` (200 Hz) **when the robot is first initialized** inside `load_policy`; changing physics dt after the articulation is created can invalidate the PhysX simulation view and cause **"Failed to get root link transforms from backend"** or **"Simulation view object is invalidated"**. So the correct order is: scene → robot → start simulation → start_g1_policy_walk (which loads policy, sets dt, then creates the articulation).
- If you use a **pre-made scene** (e.g. from a USD or template), set the scene’s physics step to **0.005 s** (200 Hz) in the stage/settings so that with decimation 4 the policy runs at 50 Hz.

### Checklist

| Check | What to do |
|-------|------------|
| **Physics dt** | 0.005 s (200 Hz). Confirm in log or scene settings. |
| **Scene order** | `create_physics_scene` → `create_robot` (g1_minimal) → `start_g1_policy_walk`. |
| **PD gains** | Extension applies Isaac Lab–matching gains (legs 150/200, ankles 20, arms 40). No change needed unless you altered the robot USD. |
| **Rough vs nav policy** | If the **rough** walking policy (e.g. flat 123-dim) walks but the **nav** policy (310-dim with height scan) falls, try the same scene and dt with the rough policy to confirm timing; nav policy can be more sensitive to observation/height-scan or velocity-command differences. |
