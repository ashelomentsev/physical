# Git cleanup – remove large files from history

## What’s using space

- **.git/objects** ≈ 627 MB, mostly from:
  - **US_Nebius.usdz** (~576 MB) – was committed, then removed; still stored in history.
  - **artefacts.zip** (~84.5 MB) – still in working tree and history.

## Option A: git-filter-repo (recommended)

1. **Install** (one-time):
   ```bash
   brew install git-filter-repo
   ```

2. **Remove specific files from all history** (run from repo root):
   ```bash
   cd /Users/andreys/Sites/modern/physical

   # Remove the big .usdz (and optionally artefacts.zip) from entire history
   git filter-repo --path scene_files/US_Nebius.usdz --invert-paths --force
   # Optional: also remove artefacts.zip from history (file will remain in working tree until you delete it):
   # git filter-repo --path scene_files/artefacts.zip --invert-paths --force
   ```

3. **Re-add remote** (filter-repo removes remotes for safety):
   ```bash
   git remote add origin <your-remote-url>
   ```

4. **Reclaim space**:
   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

5. **If you already pushed this history**, force-push (rewrites history; coordinate with others):
   ```bash
   git push --force origin main
   ```

---

## Option B: BFG Repo Cleaner

1. **Install**: `brew install bfg`

2. **Delete the large file from history**:
   ```bash
   cd /Users/andreys/Sites/modern/physical
   bfg --delete-files US_Nebius.usdz
   # Optional: bfg --delete-files artefacts.zip
   ```

3. **Clean up**:
   ```bash
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

4. **Force-push** if you had already pushed: `git push --force origin main`

---

## Option C: Only stop tracking large files (no history rewrite)

If you don’t care about shrinking existing clones and only want to avoid adding more big files:

1. Add to **.gitignore**:
   ```
   scene_files/US_Nebius.usdz
   scene_files/*.usdz
   scene_files/artefacts.zip
   ```

2. Remove from the index (keeps file on disk):
   ```bash
   git rm --cached scene_files/artefacts.zip
   git commit -m "Stop tracking artefacts.zip"
   ```

3. Run a normal gc (won’t remove old US_Nebius.usdz from history):
   ```bash
   git gc --prune=now
   ```

This reduces future growth but **does not** reduce the current 627 MB .git size; for that you need Option A or B.

---

## After cleanup

- **Option A or B**: `.git` should drop to roughly the size of the remaining history (likely well under 100 MB).
- **Option C**: `.git` stays large; only new commits stay smaller.

Recommendation: use **Option A** (git-filter-repo) to remove `US_Nebius.usdz` (and optionally `artefacts.zip`) from history, then add the same paths to `.gitignore` so they are never committed again.
