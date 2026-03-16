from pathlib import Path


path = Path("/home/splatica/isaac-sim-mcp/isaac.sim.mcp_extension/isaac_sim_mcp_extension/extension.py")
text = path.read_text()

old = '''            last_error = None
            used_asset = None
            for asset_path in candidate_paths:
                try:
                    add_reference_to_stage(asset_path, "/G1")
                    used_asset = asset_path
                    break
                except Exception as e:
                    last_error = str(e)
'''

new = '''            last_error = None
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
'''

if old not in text:
    raise SystemExit("target create_robot block not found")

path.write_text(text.replace(old, new, 1))
print("PATCHED_G1_DELETE_FIX")
