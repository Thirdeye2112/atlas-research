p = r'src\atlas_research\db\repository.py'
c = open(p).read()

old1 = 'import json as _json\n\n    hyperparams = record.get("hyperparams")\n    fold_metrics = record.get("fold_metrics")'
new1 = '''import json as _json
    import math as _math
    hyperparams = record.get("hyperparams")
    fold_metrics = record.get("fold_metrics")

    def _sanitise_for_json(obj):
        if isinstance(obj, float):
            return None if (_math.isnan(obj) or _math.isinf(obj)) else obj
        if isinstance(obj, dict):
            return {k: _sanitise_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitise_for_json(v) for v in obj]
        return obj'''

old2 = '"hyperparams":     _json.dumps(hyperparams) if hyperparams else None,'
new2 = '"hyperparams":     _json.dumps(_sanitise_for_json(hyperparams)) if hyperparams else None,'

old3 = '"fold_metrics":    _json.dumps(fold_metrics) if fold_metrics else None,'
new3 = '"fold_metrics":    _json.dumps(_sanitise_for_json(fold_metrics)) if fold_metrics else None,'

if old1 not in c:
    print("ERROR: target block 1 not found — print context:")
    idx = c.find('fold_metrics = record.get')
    print(repr(c[max(0,idx-200):idx+100]))
else:
    c = c.replace(old1, new1, 1)
    c = c.replace(old2, new2, 1)
    c = c.replace(old3, new3, 1)
    open(p, 'w').write(c)
    result = open(p).read()
    if '_sanitise_for_json' in result:
        print('PATCHED OK — run: python scripts/run_training.py')
    else:
        print('FAILED — sanitise not found after write')
