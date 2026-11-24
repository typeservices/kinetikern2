"""Replay two frozen uncorrected settings to capture the engine entry precedence.

Does not rematch looseness or change original observations. Adds runtime baseline
metadata after verifying each replay reproduces the stored pair gaps.
"""
import argparse
import json
import hashlib
import math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import kk3_fonts as kf
import kk3_bridge as kb
from kk3_fontz_reference import cached_case
from kk3_fontz_runner import Runner
from kk3_fontz_corpus import atomic_json,digest_json
from kk3_fontz_observe import CHARS
from kk3_fontz_paths import observation_path
from kk3_fontz_fit import predict_applied

def enrich(args):
    path,root,cache,identity=args;path=Path(path);o=json.loads(path.read_text())
    if o.get('runtime_identity')==identity:return str(path)
    if o['protocol']['engine']!=identity['engine']:raise ValueError('Engine changed')
    case=cached_case(Path(root)/o['path'],Path(cache),CHARS,expected_sha=o['sha256'])
    runner=Runner({'font':case},threads=1);n=len(o['glyphs']);unit=1000/case['upm']
    left=[p['left'] for p in case['pairs']];right=[p['right'] for p in case['pairs']]
    baselines={}
    try:
        for setting,L,key in [('matched',o['looseness'],'model'),('fixed',0,'fixed_model')]:
            params=kb.make_params(spring=math.exp(-.55*L),repulsion=3.86*math.exp(.55*L),coupling=1,
                classes=True,window=True,scope_scripts=True,threshold=5/unit,budget=0,threads=1)
            result=kf.run_job(runner.engine.solve(runner.contexts['font'],params,punctuation=runner.punctuation['font']))
            try:
                kern=np.array(result.values(left,right)).reshape(n,n)*unit
                metrics=result.metrics
                gaps=np.array([metrics[i].rsb+metrics[j].lsb for i,j in zip(left,right)]).reshape(n,n)*unit+kern
                if not np.allclose(gaps,o[key],atol=1e-7,rtol=0):raise ValueError('Replay differs from frozen baseline: '+o['path'])
                explicit=np.zeros((n,n),dtype=bool)
                for kind,i,j,v,importance in result.iter_entries():
                    if kind==kb.ENTRY_GLYPH_GLYPH:explicit[i,j]=True
                baselines[setting]={'kerning':kern.tolist(),'explicit':explicit.tolist()}
            finally:result.close()
            # An actual-engine parity probe covers below/above threshold and side shifts.
            pairs=[(i,j,3.0 if (i+j)%2 else 7.0) for i in range(n) for j in range(n) if (i+j)%7==0]
            sides=[[1/unit,2/unit] for _ in range(n)]
            corrected=kf.run_job(runner.engine.solve(runner.contexts['font'],params,punctuation=runner.punctuation['font'],harness=(sides,[(i,j,d/unit) for i,j,d in pairs])))
            try:
                m=corrected.metrics;actual=np.array([m[i].rsb+m[j].lsb+k for i,j,k in zip(left,right,corrected.values(left,right))]).reshape(n,n)*unit
                t={'glyphs':o['glyphs'],'stem_ref':85,'stem_range':[1,1000],'looseness_range':[-1,1],
                   'left':{x:[1,0,0,0] for x in o['glyphs']},'right':{x:[2,0,0,0] for x in o['glyphs']},
                   'pairs':{o['glyphs'][i]+' '+o['glyphs'][j]:d for i,j,d in pairs}}
                predicted=gaps+predict_applied(t,L,o['stem'],baselines[setting])
                if not np.allclose(actual,predicted,atol=.001,rtol=0):raise ValueError('Engine correction parity failed: '+o['path'])
            finally:corrected.close()
    finally:runner.close()
    o['runtime_baselines']=baselines;o['runtime_identity']=identity;atomic_json(path,o);return str(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    run=a.run;index=json.loads((run/'data/index.json').read_text());manifest=json.loads((run/'manifest.json').read_text())
    paths=[str(observation_path(run/'data',r['observation'])) for r in index['records'] if 'observation' in r]
    files=[Path(__file__),Path(kb.__file__),Path(kf.__file__),Path(__file__).with_name('kk3_fontz_runner.py'),Path(__file__).with_name('kk3_fontz_fit.py')]
    identity={'engine':hashlib.sha256(Path(kf.DYLIB).read_bytes()).hexdigest(),'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'parity_tolerance_per_1000':.001}
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i,path in enumerate(pool.map(enrich,[(p,manifest['root'],str(run/'data/cache/references'),identity) for p in paths])):
            print('%d/%d replay and engine parity passed'%(i+1,len(paths)),flush=True)
    atomic_json(run/'runtime-enrichment.json',identity)
if __name__=='__main__':main()
