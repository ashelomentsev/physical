from pathlib import Path


path = Path("/home/splatica/isaac-sim-mcp/isaac.sim.mcp_extension/isaac_sim_mcp_extension/extension.py")
text = path.read_text()

old = '''            for asset_path in candidate_paths:
                try:
                    add_reference_to_stage(asset_path, "/G1")
                    used_asset = asset_path
                    break
                except Exception as e:
                    last_error = str(e)
'''

new = '''            for asset_path in candidate_paths:
                try:
                    add_reference_to_stage(asset_path, "/G1")
                    prim = stage.GetPrimAtPath("/G1")
                    refs = prim.GetMetadata("references") if prim and prim.IsValid() else None
                    if refs is not None:
                        used_asset = asset_path
                        break
                    omni.kit.commands.execute("DeletePrims", paths=["/G1"])
                    last_error = f"Reference metadata missing for {asset_path}"
                except Exception as e:
                    last_error = str(e)
'''

if old not in text:
    raise SystemExit("target loop block not found")

path.write_text(text.replace(old, new, 1))
print("PATCHED_G1_REFERENCE_VERIFY")
