"""Check the exported profiles through the plugin Plan and the actual K3 engine.

The offline snapshot has fontTools outlines instead of Cocoa paths. Supply its
independently measured stem to Plan; all correction mapping and coefficients run
through the production implementation. This is not an in-Glyphs UI test.
"""
from concurrent.futures import ProcessPoolExecutor
import argparse
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch
import numpy as np
import kk3_fonts as kf
import kk3_bridge as kb
import kk3_harness as kh
import kk3_harness_profiles as profiles
from kk3_fontz_corpus import atomic_json, digest_json
from kk3_fontz_reference import cached_case
from kk3_fontz_observe import CHARS
from kk3_fontz_runner import Runner
from kk3_fontz_paths import observation_path
from kk3_fontz_fit import predict_applied


def _verify_record(args):
    run,root,record,table,bundled=args
    worst=0.
    checked=0
    obs = json.loads(observation_path(run/'data',record['observation']).read_text())
    case = cached_case(Path(root) / obs['path'], run / 'data/cache/references', CHARS,
                       expected_sha=obs['sha256'])
    runner = Runner({'font':case})
    n = len(obs['glyphs'])
    left = [p['left'] for p in case['pairs']]
    right = [p['right'] for p in case['pairs']]
    unit = 1000 / case['upm']
    try:
        for setting, looseness, key in [('matched', obs['looseness'], 'model'), ('fixed', 0., 'fixed_model')]:
            params = kb.make_params(spring=math.exp(-.55*looseness), repulsion=3.86*math.exp(.55*looseness),
                                    coupling=1, classes=True, window=True, scope_scripts=True,
                                    threshold=5/unit, budget=0, threads=1, style='text')
            for label, selected in [('Google Fonts', bundled), ('Fontz', table)]:
                with patch.object(kh, 'stem_per_1000', return_value=obs['stem']):
                    plan = kh.Plan(runner.snapshots['font'], looseness, 1., style='text',
                                   punctuation=True, profile=selected)
                result = kf.run_job(runner.engine.solve(runner.contexts['font'], params,
                                   punctuation=runner.punctuation['font'], harness=plan.engine_arg()))
                try:
                    metrics = result.metrics
                    gaps = np.array([metrics[i].rsb+metrics[j].lsb+k for i,j,k in
                                     zip(left,right,result.values(left,right))]).reshape(n,n)*unit
                finally:
                    result.close()
                expected = np.asarray(obs[key])+predict_applied(selected,looseness,obs['stem'],obs['runtime_baselines'][setting])
                error = float(np.max(np.abs(gaps-expected)))
                if not np.isfinite(error) or error > .001:
                    raise ValueError('%s %s %s parity error %.8f' % (obs['path'],setting,label,error))
                worst = max(worst,error)
                checked += 1
    finally:
        runner.close()
    return checked,worst


def verify(run, limit=None, workers=6):
    run = Path(run)
    manifest = json.loads((run / 'manifest.json').read_text())
    engine_sha=hashlib.sha256(Path(kf.DYLIB).read_bytes()).hexdigest()
    if engine_sha != profiles.engine_identity()['sha256']:
        raise ValueError('KK3_DYLIB override differs from the bundled/profile engine')
    table = profiles.validate_profile(json.loads((run / 'fontz-harness.json').read_text()), profiles.engine_identity())
    bundled = json.loads((run / 'google-fonts-comparison.json').read_text())
    index = json.loads((run / 'data/index.json').read_text())
    records = [r for r in index['records'] if 'observation' in r]
    if limit:
        records = records[:limit]
    worst = 0.
    checked = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs=[(run,manifest['root'],record,table,bundled) for record in records]
        for count,error in pool.map(_verify_record,jobs):
            checked += count
            worst = max(worst,error)
            print('%d profile/settings checks; max difference %.8f' % (checked,worst),flush=True)
    result = dict(fonts=len(records),checks=checked,max_error_per_1000=worst,tolerance=.001,
                  profile_digest=digest_json(table),engine_sha256=engine_sha,
                  source_sha256=hashlib.sha256(Path(kh.__file__).read_bytes()).hexdigest(),
                  note='Offline production Plan and actual-engine parity; Cocoa stem extraction and UI still need Glyphs review.')
    atomic_json(run/('runtime-verification-pilot.json' if limit else 'runtime-verification.json'),result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    print(json.dumps(verify(args.run,args.limit,args.workers),indent=2))
