"""Local, resumable observations from the exact plugin engine, without corrections."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import fontTools
import uharfbuzz
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
import kk3_fonts as kf
import kk3_bridge as kb
from kk3_fontz_runner import Runner
from kk3_fontz_reference import cached_case, UnsupportedReference
from kk3_fontz_corpus import atomic_json, digest_json

RES = Path(kb.__file__).parent
NAMES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'period', 'comma', 'colon', 'semicolon', 'exclam', 'question', 'hyphen', 'quotesingle', 'quotedbl', 'parenleft', 'parenright', 'slash', 'ampersand', 'quoteright']
from kk3_fontz_fit import project_table
BUNDLED = project_table(json.loads((RES/'kk3_harness.json').read_text()), NAMES)
PUNCT = dict(zip(['period','comma','colon','semicolon','exclam','question','hyphen','quotesingle','quotedbl','parenleft','parenright','slash','ampersand','quoteright'], '.,:;!?-\'"()/&’'))
CHARS = ''.join(n if len(n)==1 else PUNCT[n] for n in NAMES)

def protocol():
    files = [Path(__file__), Path(kf.__file__), Path(kb.__file__), Path(__file__).with_name('kk3_fontz_reference.py'), Path(__file__).with_name('kk3_fontz_runner.py'), Path(kf.DYLIB), RES/'kk3_punctuation.py', RES/'kk3_punctuation.json']
    return dict(schema='fontz-k3-observation/1', engine=hashlib.sha256(Path(kf.DYLIB).read_bytes()).hexdigest(),
                sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                dependencies={'numpy':np.__version__,'fontTools':fontTools.__version__,'uharfbuzz':uharfbuzz.__version__},
                punctuation_sha256=hashlib.sha256((RES/'kk3_punctuation.json').read_bytes()).hexdigest(),
                convention='text', punctuation=True, chars=CHARS, base='Kinetikern3', harness='off', classes=True, threshold=5, budget=0,
                looseness_bounds=[-1,1], grid=41, tolerance=.001, offset='median designer-minus-model gap')

def observation_identity(row, settings):
    return digest_json({'font':row['sha256'],'face':row.get('face_index',0),'protocol':settings})

def validate_case(case, chars=CHARS):
    if ''.join(case['characters']) != chars:
        raise UnsupportedReference('incomplete or aliased 66-character core')
    if case['skipped'] or len(case['pairs']) != len(chars)**2:
        raise UnsupportedReference('substitution or unsupported pair shaping in core')

def normalized_gaps(case):
    n=round(math.sqrt(len(case['pairs'])))
    matrix=np.full((n,n),np.nan)
    for p in case['pairs']:matrix[p['left'],p['right']]=p['gap']*1000/case['upm']
    if not np.isfinite(matrix).all():raise UnsupportedReference('nonfinite or incomplete pair matrix')
    return matrix

def match_looseness(target, solve):
    cache={}
    def evaluate(x):
        x=round(float(x),8)
        if x not in cache:
            m=solve(x); cache[x]=(float(np.abs(target-m).mean()),m)
        return cache[x][0]
    grid=np.linspace(-1,1,41); best=min(grid,key=evaluate)
    lo=max(-1,best-.05); hi=min(1,best+.05)
    # Fixed deterministic refinement; no harness-specific matching.
    while hi-lo>.001:
        a=lo+(hi-lo)/3;b=hi-(hi-lo)/3
        if evaluate(a)<=evaluate(b):hi=b
        else:lo=a
    evaluate((lo+hi)/2)
    winner=min(cache,key=lambda x:(cache[x][0],abs(x),x))
    return winner,cache[winner][1]

class OutlinePen(BasePen):
    def __init__(self,glyphset):super().__init__(glyphset);self.polys=[];self.poly=[]
    def _moveTo(self,p):self.poly=[p];self.polys.append(self.poly)
    def _lineTo(self,p):self.poly.append(p)
    def _curveToOne(self,a,b,c):
        p=self._getCurrentPoint()
        for t in np.linspace(1/24,1,24):
            self.poly.append(tuple((1-t)**3*p[k]+3*(1-t)**2*t*a[k]+3*(1-t)*t*t*b[k]+t**3*c[k] for k in (0,1)))
    def _qCurveToOne(self,a,b):
        p=self._getCurrentPoint()
        for t in np.linspace(1/24,1,24):self.poly.append(tuple((1-t)**2*p[k]+2*(1-t)*t*a[k]+t*t*b[k] for k in (0,1)))
    def _closePath(self):pass
    def _endPath(self):pass

def font_stem(font):
    glyphset=font.getGlyphSet(); cmap=font.getBestCmap() or {}
    for ch in 'Il':
        if ord(ch) not in cmap:continue
        pen=OutlinePen(glyphset);glyphset[cmap[ord(ch)]].draw(pen)
        ys=[y for poly in pen.polys for x,y in poly]
        if not ys:continue
        y=(min(ys)+max(ys))/2+.37;xs=[]
        for poly in pen.polys:
            for (x0,y0),(x1,y1) in zip(poly,poly[1:]+poly[:1]):
                if y0<=y<y1 or y1<=y<y0:xs.append(x0+(y-y0)*(x1-x0)/(y1-y0))
        xs.sort()
        if len(xs)>=2 and xs[1]>xs[0]:return (xs[1]-xs[0])*1000/font['head'].unitsPerEm
    raise UnsupportedReference('no measurable I or l stem')

def observe_font(row, engine=None, protocol=None):
    """row includes root/cache; engine argument reserved for caller compatibility."""
    settings=protocol or globals()['protocol']();path=Path(row['root'])/row['path']
    identity=observation_identity(row,settings)
    with TTFont(path,fontNumber=row.get('face_index',0)) as f:
        if f['post'].isFixedPitch:raise UnsupportedReference('monospace outside proportional scope')
        stem=font_stem(f)
    case=cached_case(path,Path(row['cache'])/'references',CHARS,expected_sha=row['sha256'])
    validate_case(case);target=normalized_gaps(case)
    runner=Runner({'font':case},threads=1)
    def solve(L):
        p=kb.make_params(spring=math.exp(-.55*L),repulsion=3.86*math.exp(.55*L),coupling=1,
                        classes=True,window=True,scope_scripts=True,threshold=5*case['upm']/1000,budget=0,threads=1)
        result=kf.run_job(runner.engine.solve(runner.contexts['font'],p,punctuation=runner.punctuation['font']))
        try:
            left=[v['left'] for v in case['pairs']];right=[v['right'] for v in case['pairs']]
            kern=result.values(left,right);m=result.metrics
            return np.array([m[i].rsb+m[j].lsb+k for i,j,k in zip(left,right,kern)]).reshape(len(NAMES),len(NAMES))*1000/case['upm']
        finally:result.close()
    try:
        fixed=solve(0);L,model=match_looseness(target,solve)
    finally:runner.close()
    raw=target-model;offset=float(np.median(raw))
    return dict(schema=settings['schema'],identity=identity,protocol=settings,path=row['path'],sha256=row['sha256'],
                cluster=row['cluster'],split=row['split'],upm=case['upm'],glyphs=NAMES,mapping=case['names'],
                stem=stem,looseness=L,boundary=abs(L)>=.999,offset=offset,
                target=target.tolist(),model=model.tolist(),fixed_model=fixed.tolist(),residual=(raw-offset).tolist())

def _worker(args):
    row,settings,out=args; dest=Path(out)/(observation_identity(row,settings)+'.json')
    if hashlib.sha256((Path(row['root'])/row['path']).read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Font changed since manifest freeze: '+row['path'])
    if dest.exists():
        data=json.loads(dest.read_text())
        if data.get('identity')!=observation_identity(row,settings):raise ValueError('cache identity mismatch')
        return dict(path=row['path'],cluster=row['cluster'],split=row['split'],observation=str(dest),cached=True)
    try:
        obs=observe_font(row,protocol=settings);atomic_json(dest,obs)
        return dict(path=row['path'],cluster=row['cluster'],split=row['split'],observation=str(dest))
    except UnsupportedReference as e:return dict(path=row['path'],cluster=row['cluster'],split=row['split'],exclusion=str(e))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);ap.add_argument('--workers',type=int,default=2);ap.add_argument('--limit',type=int)
    a=ap.parse_args();m=json.loads(Path(a.manifest).read_text());out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    settings=protocol();atomic_json(out/'protocol.json',settings)
    rows=[dict(r,root=m['root'],cache=str(out/'cache')) for r in m['fonts'] if r['selected']]
    if a.limit:rows=rows[:a.limit]
    records=[{k:r[k] for k in ('path','cluster','split','exclusion')} for r in m['fonts'] if not r['selected']]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i,r in enumerate(pool.map(_worker,[(r,settings,str(out/'observations')) for r in rows])):
            records.append(r);atomic_json(out/'index.json',dict(manifest=m['digest'],protocol=digest_json(settings),records=records))
            print('%d/%d %s %s'%(i+1,len(rows),r['path'],r.get('exclusion','OK')),flush=True)
if __name__=='__main__':main()
