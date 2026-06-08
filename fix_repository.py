import os, sys

p = os.path.join('src', 'atlas_research', 'db', 'repository.py')
c = open(p).read()

if '_sanitise_for_json' in c:
    print('already patched')
    sys.exit(0)

# Insert math import
c = c.replace(
    '    import json as _json\n\n    hyperparams',
    '    import json as _json\n    import math as _math\n\n    hyperparams'
)

# Insert sanitise function after fold_metrics assignment
c = c.replace(
    '    hyperparams = record.get("hyperparams")\n    fold_metrics = record.get("fold_metrics")',
    '    hyperparams = record.get("hyperparams")\n    fold_metrics = record.get("fold_metrics")\n\n    def _sanitise_for_json(obj):\n        if isinstance(obj, float):\n            return None if (_math.isnan(obj) or _math.isinf(obj)) else obj\n        if isinstance(obj, dict):\n            return {k: _sanitise_for_json(v) for k, v in obj.items()}\n        if isinstance(obj, list):\n            return [_sanitise_for_json(v) for v in obj]\n        return obj'
)

# Wrap json.dumps calls
c = c.replace(
    '_json.dumps(hyperparams) if hyperparams',
    '_json.dumps(_sanitise_for_json(hyperparams)) if hyperparams'
)
c = c.replace(
    '_json.dumps(fold_metrics) if fold_metrics',
    '_json.dumps(_sanitise_for_json(fold_metrics)) if fold_metrics'
)

open(p, 'w').write(c)

if '_sanitise_for_json' in open(p).read():
    print('PATCHED OK — run: python scripts/run_training.py')
else:
    print('PATCH FAILED — printing the fold_metrics section for diagnosis:')
    idx = c.find('fold_metrics = record.get')
    print(c[max(0,idx-100):idx+600])
