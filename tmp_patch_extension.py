from pathlib import Path


path = Path("/home/splatica/isaac-sim-mcp/isaac.sim.mcp_extension/isaac_sim_mcp_extension/extension.py")
text = path.read_text()
orig = text

text = text.replace(
    '        self._text_prompt_cache = {} # cache for text prompt\n        \n',
    '        self._text_prompt_cache = {} # cache for text prompt\n        self._script_globals = {}\n        \n',
    1,
)

old_exec = '''    def execute_script(self, code: str) :
        """Execute a Python script within the Isaac Sim context.
        
        Args:
            code: The Python script to execute.
            
        Returns:
            Dictionary with execution result.
        """
        try:
            # Create a local namespace
            local_ns = {}
            
            # Add frequently used modules to the namespace
            local_ns["omni"] = omni
            local_ns["carb"] = carb
            local_ns["Usd"] = Usd
            local_ns["UsdGeom"] = UsdGeom
            local_ns["Sdf"] = Sdf
            local_ns["Gf"] = Gf
            # code = script["code"]
            
            # Execute the script
            exec(code,  local_ns)
            
            # Get the result if any
            # result = local_ns.get("result", None)
            result = None
            
            
            return {
                "status": "success",
                "message": "Script executed successfully",
                "result": result
            }
        except Exception as e:
            carb.log_error(f"Error executing script: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
            return {
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
'''

new_exec = '''    def execute_script(self, code: str) :
        """Execute a Python script within the Isaac Sim context.
        
        Args:
            code: The Python script to execute.
            
        Returns:
            Dictionary with execution result.
        """
        try:
            # Keep a persistent namespace so helper functions and callback state
            # survive across MCP calls.
            local_ns = self._script_globals
            
            # Add frequently used modules to the namespace
            local_ns["omni"] = omni
            local_ns["carb"] = carb
            local_ns["Usd"] = Usd
            local_ns["UsdGeom"] = UsdGeom
            local_ns["Sdf"] = Sdf
            local_ns["Gf"] = Gf
            local_ns["np"] = np
            local_ns["time"] = time
            local_ns["json"] = json
            local_ns["traceback"] = traceback
            local_ns["_physx"] = _physx
            local_ns["timeline"] = omni.timeline.get_timeline_interface()
            local_ns["World"] = World
            local_ns["extension"] = self
            
            # Execute the script
            exec(code, local_ns)
            
            # Return the script-defined result if present.
            result = local_ns.get("result", None)
            
            return {
                "status": "success",
                "message": "Script executed successfully",
                "result": result
            }
        except Exception as e:
            carb.log_error(f"Error executing script: {e}")
            import traceback as tb
            carb.log_error(tb.format_exc())
            return {
                "status": "error",
                "message": str(e),
                "traceback": tb.format_exc()
            }
'''

if old_exec not in text:
    raise SystemExit("old execute_script block not found")
text = text.replace(old_exec, new_exec, 1)

old_g1 = '''        elif robot_type.lower() == "g1":
            asset_path = assets_root_path + "/Isaac/Robots/Unitree/G1/g1.usd"
            add_reference_to_stage(asset_path, "/G1")
            robot_prim = XFormPrim(prim_path="/G1")
            robot_prim.set_world_pose(position=np.array(position))
            return {"status": "success", "message": f"{robot_type} robot created"}
'''

new_g1 = '''        elif robot_type.lower() in ["g1", "g1_minimal"]:
            robot_kind = robot_type.lower()
            candidate_paths = []
            if robot_kind == "g1_minimal":
                candidate_paths.append(assets_root_path + "/Isaac/Robots/Unitree/G1/g1_minimal.usd")
            candidate_paths.append(assets_root_path + "/Isaac/Robots/Unitree/G1/g1.usd")

            last_error = None
            used_asset = None
            existing_prim = stage.GetPrimAtPath("/G1")
            if existing_prim and existing_prim.IsValid():
                omni.kit.commands.execute("DeletePrims", paths=["/G1"])
            for asset_path in candidate_paths:
                try:
                    add_reference_to_stage(asset_path, "/G1")
                    used_asset = asset_path
                    break
                except Exception as e:
                    last_error = str(e)

            if used_asset is None:
                raise RuntimeError(f"Failed to load {robot_type} asset: {last_error}")

            robot_prim = XFormPrim(prim_path="/G1")
            robot_prim.set_world_pose(position=np.array(position))
            message = f"{robot_type} robot created"
            if robot_kind == "g1_minimal" and used_asset.endswith('/g1.usd'):
                message += " (fallback to g1.usd; minimal asset not found)"
            return {"status": "success", "message": message, "asset_path": used_asset}
'''

if old_g1 not in text:
    raise SystemExit("old g1 block not found")
text = text.replace(old_g1, new_g1, 1)

if text == orig:
    raise SystemExit("no changes made")

path.write_text(text)
print("PATCHED_EXTENSION")
