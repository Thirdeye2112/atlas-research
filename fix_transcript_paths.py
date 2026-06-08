"""
Fix sys.path in transcript scripts so 'config' module is importable.
Run from the repo root: python fix_transcript_paths.py
"""
import os

ROOT_LINE = "sys.path.insert(0, str(ROOT))"

targets = [
    os.path.join('scripts', 'run_transcript_pipeline.py'),
    os.path.join('scripts', 'inspect_hypotheses.py'),
]

for fpath in targets:
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fpath}")
        continue
    c = open(fpath).read()
    src_line = 'sys.path.insert(0, str(ROOT / "src"))'
    if ROOT_LINE in c:
        print(f"already fixed: {fpath}")
        continue
    if src_line in c:
        c = c.replace(src_line, src_line + "\n" + ROOT_LINE)
        open(fpath, 'w').write(c)
        print(f"FIXED: {fpath}")
    else:
        print(f"WARNING: expected sys.path line not found in {fpath}")

# Also fix the module files that import from config
module_targets = [
    os.path.join('src', 'atlas_research', 'transcripts', 'extractor.py'),
    os.path.join('src', 'atlas_research', 'transcripts', 'backtester.py'),
    os.path.join('src', 'atlas_research', 'transcripts', 'promoter.py'),
]

for fpath in module_targets:
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fpath}")
        continue
    c = open(fpath).read()
    if 'from config import settings' not in c:
        print(f"no config import: {fpath}")
        continue
    # These are imported as modules; they rely on the caller having set sys.path.
    # The fix is in the scripts, not here. Just verify.
    print(f"OK (uses config, fixed via script paths): {fpath}")

print("\nDone. Now run:")
print("  python scripts/run_training.py")
