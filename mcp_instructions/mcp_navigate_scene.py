#!/usr/bin/env python3
"""
MCP client script that directly sends commands to the Isaac Sim extension socket
to set up a scene with obstacles and navigate the G1 robot through them.

Scene layout and coordinates are defined in:
  workspace/docs/planner/OBSTACLE_SCENE_MAP_DRAFT.md

Steps:
  1. get_scene_info        -- verify connection
  2. create_physics_scene   -- floor + 2 obstacle cubes (from map draft)
  3. create_robot           -- G1 minimal at (1, 1, 0.74)
  4. start_g1_policy_walk   -- activate locomotion policy
  5. navigate_to            -- target (10, 10) with obstacle boxes
  6. get_navigation_status  -- poll a few times
"""

import socket
import json
import time
import sys

HOST = "localhost"
PORT = 8766
TIMEOUT = 60.0

# Policy path inside the Isaac Sim Docker container
POLICY_PATH = "/home/workspace/exported/g1_flat_policy.pt"


def send_command(sock, command_type: str, params: dict = None) -> dict:
    """Send a JSON command to the Isaac Sim extension and return the parsed response."""
    command = {"type": command_type, "params": params or {}}
    payload = json.dumps(command).encode("utf-8")
    sock.sendall(payload)

    # Receive full response
    chunks = []
    sock.settimeout(TIMEOUT)
    while True:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            # Try to parse accumulated data as JSON
            try:
                data = b"".join(chunks)
                result = json.loads(data.decode("utf-8"))
                return result
            except json.JSONDecodeError:
                continue
        except socket.timeout:
            break

    if chunks:
        data = b"".join(chunks)
        try:
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            return {"status": "error", "message": f"Incomplete JSON: {data[:200]}"}
    return {"status": "error", "message": "No data received"}


def extract_result(response: dict) -> dict:
    """Extract result from response, handling error status."""
    if response.get("status") == "error":
        return {"error": response.get("message", "Unknown error")}
    return response.get("result", response)


def main():
    # Connect to the Isaac Sim extension socket
    print("=" * 70)
    print("Connecting to Isaac Sim extension at {}:{}".format(HOST, PORT))
    print("=" * 70)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("ERROR: Could not connect to Isaac Sim extension at {}:{}".format(HOST, PORT))
        print("Make sure Isaac Sim is running with the MCP extension enabled.")
        sys.exit(1)

    print("Connected successfully.\n")

    # -----------------------------------------------------------------------
    # Step 1: Verify connection
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 1: get_scene_info -- Verify MCP connection")
    print("=" * 70)
    resp = send_command(sock, "get_scene_info")
    result = extract_result(resp)
    print("Response: {}".format(json.dumps(result, indent=2)))
    print()

    # We need to reconnect for each command since the extension may close
    # the connection after each response. Let's try reusing first.
    # If it fails, we reconnect.

    # -----------------------------------------------------------------------
    # Step 2: Create physics scene with obstacles
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 2: create_physics_scene -- Floor + 2 obstacle cubes")
    print("=" * 70)

    # Obstacle positions and sizes from OBSTACLE_SCENE_MAP_DRAFT.md
    objects = [
        {
            "type": "Cube",
            "name": "obstacle_wall_1",
            "path": "/World/obstacle_wall_1",
            "position": [4.5, 3.5, 0.5],
            "scale": [1.0, 4.0, 1.0],
            "color": [0.8, 0.2, 0.2, 1.0],
            "physics_enabled": True,
            "is_kinematic": True,
        },
        {
            "type": "Cube",
            "name": "obstacle_wall_2",
            "path": "/World/obstacle_wall_2",
            "position": [7.5, 7.5, 0.5],
            "scale": [4.0, 1.0, 1.0],
            "color": [0.2, 0.2, 0.8, 1.0],
            "physics_enabled": True,
            "is_kinematic": True,
        },
    ]

    # Reconnect for next command
    sock.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    resp = send_command(sock, "create_physics_scene", {
        "objects": objects,
        "floor": True,
        "gravity": [0, 0, -9.81],
        "scene_name": "physics_scene",
        "floor_type": "flat",
    })
    result = extract_result(resp)
    print("Response: {}".format(json.dumps(result, indent=2)))
    print()

    # -----------------------------------------------------------------------
    # Step 3: Spawn the G1 robot
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 3: create_robot -- G1 minimal at [1, 1, 0.74]")
    print("=" * 70)

    sock.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    resp = send_command(sock, "create_robot", {
        "robot_type": "g1_minimal",
        "position": [1.0, 1.0, 0.74],
    })
    result = extract_result(resp)
    print("Response: {}".format(json.dumps(result, indent=2)))
    print()

    # -----------------------------------------------------------------------
    # Step 4: Start the walking policy
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 4: start_g1_policy_walk -- Activate locomotion policy")
    print("=" * 70)

    sock.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    resp = send_command(sock, "start_g1_policy_walk", {
        "policy_path": POLICY_PATH,
        "robot_prim_path": "/G1",
        "target_velocity": 0.5,
        "deterministic": True,
    })
    result = extract_result(resp)
    print("Response: {}".format(json.dumps(result, indent=2)))
    print()

    # Give the policy a moment to initialize and stabilize
    print("Waiting 3 seconds for policy to stabilize...")
    time.sleep(3)

    # -----------------------------------------------------------------------
    # Step 5: Navigate to destination (10, 10)
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 5: navigate_to -- Target [10.0, 10.0] with obstacle avoidance")
    print("=" * 70)

    # The navigate_to tool is MCP-server-side (A* planning happens in the
    # MCP Python server, not in the Isaac Sim extension). So we need to call
    # the MCP server's navigate_to, which internally uses the socket to
    # send velocity commands.
    #
    # However, since we are directly talking to the Isaac Sim extension socket,
    # we cannot call the MCP server's navigate_to directly. Instead, we will
    # invoke the MCP server's navigate_to function by importing it.
    #
    # Let's try calling it through the MCP server's Python module.

    sock.close()

    # Import the MCP server's navigation components
    sys.path.insert(0, "/home/ubuntu/isaac-sim-mcp")
    from isaac_mcp.navigator import AStarPlanner, IsaacSimExecutor, OccupancyGrid, WaypointFollower
    from isaac_mcp.server import IsaacConnection

    import threading
    import math

    # Create a connection for navigation
    nav_lock = threading.Lock()
    isaac_conn = IsaacConnection(host=HOST, port=PORT)
    if not isaac_conn.connect():
        print("ERROR: Could not reconnect for navigation")
        sys.exit(1)

    executor = IsaacSimExecutor(isaac_conn, nav_lock, robot_prim_path="/G1")

    # Get current pose
    try:
        current_xy, current_yaw = executor.get_pose()
        print("Current robot position: [{:.2f}, {:.2f}], yaw: {:.2f} rad".format(
            current_xy[0], current_xy[1], current_yaw))
    except Exception as e:
        print("Warning: Could not get robot pose: {}".format(e))
        current_xy = [1.0, 1.0]
        current_yaw = 0.0

    # Define obstacle boxes as [cx, cy, sx, sy]
    # Obstacle 1: center (4.5, 3.5), size (1.0, 4.0) => spans x:[4.0, 5.0], y:[1.5, 5.5]
    # Obstacle 2: center (7.5, 7.5), size (4.0, 1.0) => spans x:[5.5, 9.5], y:[7.0, 8.0]
    obstacle_boxes = [
        [4.5, 3.5, 1.0, 4.0],
        [7.5, 7.5, 4.0, 1.0],
    ]

    target_x, target_y = 10.0, 10.0

    # Build occupancy grid and plan path
    grid = OccupancyGrid.from_scene_boxes(boxes=obstacle_boxes, map_size_m=20.0, resolution_m=0.1)
    grid.inflate(radius_m=0.5)
    planner = AStarPlanner(grid)
    waypoints = planner.plan(
        (float(current_xy[0]), float(current_xy[1])),
        (target_x, target_y),
    )

    if not waypoints:
        print("ERROR: No path found to target!")
        sys.exit(1)

    print("A* path found with {} waypoints.".format(len(waypoints)))
    # Print a few waypoints
    step_size = max(1, len(waypoints) // 10)
    for i in range(0, len(waypoints), step_size):
        wp = waypoints[i]
        print("  Waypoint {}: ({:.2f}, {:.2f})".format(i, wp[0], wp[1]))
    print("  Final waypoint: ({:.2f}, {:.2f})".format(waypoints[-1][0], waypoints[-1][1]))

    # Start waypoint follower
    nav_status = {"value": "navigating", "error": None}
    nav_status_lock = threading.Lock()

    def on_status_change(status: str):
        with nav_status_lock:
            nav_status["value"] = status

    follower = WaypointFollower(executor=executor, arrival_dist_m=0.5)
    follower.follow(waypoints, on_status_change=on_status_change)
    print("Navigation started toward [{:.2f}, {:.2f}]".format(target_x, target_y))
    print()

    # -----------------------------------------------------------------------
    # Step 6: Monitor navigation status
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("STEP 6: Monitoring navigation status")
    print("=" * 70)

    for poll in range(15):
        time.sleep(5)
        with nav_status_lock:
            status = nav_status["value"]

        # Try to get current pose
        try:
            pos_xy, pos_yaw = executor.get_pose()
            dist = math.hypot(target_x - pos_xy[0], target_y - pos_xy[1])
            print("Poll {}: status={}, position=[{:.2f}, {:.2f}], distance_to_target={:.2f}".format(
                poll + 1, status, pos_xy[0], pos_xy[1], dist))
        except Exception as e:
            print("Poll {}: status={}, pose_error={}".format(poll + 1, status, e))

        if status in ("arrived", "failed", "idle"):
            print("\nNavigation finished with status: {}".format(status))
            break
    else:
        print("\nNavigation still in progress after polling timeout.")

    # Final summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    with nav_status_lock:
        final_status = nav_status["value"]
    try:
        final_xy, _ = executor.get_pose()
        final_dist = math.hypot(target_x - final_xy[0], target_y - final_xy[1])
        print("Final status: {}".format(final_status))
        print("Final position: [{:.2f}, {:.2f}]".format(final_xy[0], final_xy[1]))
        print("Distance to target: {:.2f} m".format(final_dist))
    except Exception as e:
        print("Final status: {}".format(final_status))
        print("Could not read final pose: {}".format(e))

    # Clean up
    if final_status == "navigating":
        follower.stop()

    isaac_conn.disconnect()
    print("\nDone.")


if __name__ == "__main__":
    main()
