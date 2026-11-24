#!/usr/bin/env python3
"""Local font inventory, curated family clusters and reproducible data splits."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
from fontTools.ttLib import TTFont

SEED = 'fontz-v1'
# Reviewed against the supplied Fontz family names. Unknown names remain separate.
CLUSTERS = {
    'Abril': ['Abril Display','Abril Fatface','Abril Text','Abril Titling','Abril Titling Condensed','Abril Titling Narrow','Abril Titling SemiCondensed'],
    'Adelle': ['Adelle','Adelle Condensed'],
    'Alverata': ['Alverata','Alverata Informal','Alverata Irregular'],
    'Beverly Drive': ['Beverly Drive','Beverly Drive Right'],
    'Bree': ['Bree','Bree Serif'],
    'Capitolium': ['Capitolium2','CapitoliumNews 2'],
    'Coranto': ['Coranto 2','Coranto 2 Headline'],
    'Gotham': ['Gotham','Gotham Condensed','Gotham Narrow','Gotham XNarrow'],
    'Interstate': ['Interstate','Interstate Compressed','Interstate Condensed'],
    'Iro Sans': ['Iro Sans','Iro Sans Display'],
    'IvyPresto': ['IvyPresto Display','IvyPresto Text'],
    'Karmina': ['Karmina','Karmina Sans'],
    'LFT Etica': ['LFT Etica','LFT Etica Compressed','LFT Etica Condensed','LFT Etica Display','LFT Etica Sheriff'],
    'Le Monde': ['Le Monde Journal Std','Le Monde Livre Std'],
    'Lektorat': ['Lektorat Display var','Lektorat Text var'],
    'Meno': ['Meno Display Condensed','Meno Display Extra Condensed'],
    'Miller': ['Miller Banner','Miller Banner Compressed','Miller Banner Condensed','Miller Banner Extra Compressed','Miller Banner Extra Condensed','Miller Display','Miller Headline','Miller Text'],
    'Minion': ['Minion Pro','Minion Std'],
    'Neue Haas Grotesk': ['Neue Haas Grotesk Display Pro','Neue Haas Grotesk Text Pro'],
    'Parisine': ['Parisine Std','Parisine Std Clair','Parisine Std Comp','Parisine Std Comp Clair','Parisine Std Comp Gris','Parisine Std Comp Sombre','Parisine Std Gris','Parisine Std Narr','Parisine Std Narr Gris','Parisine Std Narr Sombre','Parisine Std Sombre'],
    'Presti': ['Presti Display','Presti Text'],
    'Richmond': ['Richmond Display','Richmond Text'],
    'Swear': ['Swear Display','Swear Text'],
    'Trust': ['Trust 1A','Trust 3A'],
    'Univers Next Pro': ['Univers Next Pro','Univers Next Pro UltLt Ext'],
}

def digest_json(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()

def atomic_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    # Unique temporary name prevents simultaneous writers from sharing a partial file.
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix=path.name+'.',delete=False) as f:
        tmp=f.name
        try:
            json.dump(value,f,indent=2,sort_keys=True,allow_nan=False); f.write('\n')
            f.flush(); os.fsync(f.fileno())
        except BaseException:
            os.unlink(tmp); raise
    os.replace(tmp,path)

def split_for(cluster):
    n=int(hashlib.sha256((SEED+'\0'+cluster).encode()).hexdigest()[:8],16)/2**32
    return 'tuning' if n<.6 else 'validation' if n<.8 else 'test'

def manifest_digest(manifest):
    return digest_json({k:v for k,v in manifest.items() if k not in ('root','digest')})

def finalize_rows(rows, curation=None):
    rows=sorted(rows,key=lambda r:r['path']); seen=set()
    for r in rows:
        r['split']=split_for(r['cluster']); r['fit_selected']=False
        if r['sha256'] in seen: r.update(eligible=False,reason='duplicate content')
        seen.add(r['sha256'])
    for cluster in sorted({r['cluster'] for r in rows}):
        members=[r for r in rows if r['cluster']==cluster and r['eligible']]
        queues=[]
        for italic in (False,True):
            queues.append(sorted([r for r in members if r['italic']==italic],
                                 key=lambda r:(abs(r['width']-5),abs(r['weight']-400),r['path'])))
        selected=[]
        while any(queues) and len(selected)<6:
            for q in queues:
                if q and len(selected)<6: selected.append(q.pop(0))
        for r in selected: r['fit_selected']=True
    m={'schema':1,'seed':SEED,'curation':curation or {},'fonts':rows}
    m['digest']=manifest_digest(m)
    return m

def validate_manifest(manifest):
    if manifest.get('schema')!=1 or manifest.get('seed')!=SEED: raise ValueError('Unsupported manifest schema/seed')
    if manifest.get('digest')!=manifest_digest(manifest): raise ValueError('Manifest digest mismatch: regenerate intentionally')
    for r in manifest['fonts']:
        if r['split']!=split_for(r['cluster']): raise ValueError('Family split changed')
        p=Path(r['path'])
        if p.is_absolute() or '..' in p.parts: raise ValueError('Font paths must remain relative to the root')

def build_manifest(root: Path, curation: dict) -> dict:
    aliases={name:cluster for cluster,names in CLUSTERS.items() for name in names}
    aliases.update(curation.get('clusters',{})); rows=[]
    for path in sorted(Path(root).rglob('*')):
        if path.suffix.lower() not in ('.otf','.ttf'): continue
        rel=path.relative_to(root).as_posix(); sha=hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            with TTFont(path,lazy=True) as f:
                n=f['name']; family=n.getDebugName(16) or n.getDebugName(1) or path.stem
                style=n.getDebugName(17) or n.getDebugName(2) or 'Unknown'
                cmap=f.getBestCmap() or {}; os2=f['OS/2'] if 'OS/2' in f else None
                reason='variable font: explicit instances deferred' if 'fvar' in f else 'fixed pitch' if f['post'].isFixedPitch else None
                # Some fonts mislabel fixed pitch. Detect equal advances in the Latin alphabet too.
                latin=[cmap[c] for c in range(65,123) if chr(c).isalpha() and c in cmap]
                if latin and len({f['hmtx'][g][0] for g in latin})==1: reason='fixed pitch'
                if len(latin)!=52: reason='incomplete basic Latin'
                reason=curation.get('exclude',{}).get(rel,reason)
                cluster=aliases.get(family,family)
                rows.append(dict(path=rel,sha256=sha,face_index=0,family=family,style=style,cluster=cluster,
                    weight=int(os2.usWeightClass) if os2 else 400,width=int(os2.usWidthClass) if os2 else 5,
                    italic=bool(f['head'].macStyle & 2),upm=f['head'].unitsPerEm,glyphs=f['maxp'].numGlyphs,
                    eligible=reason is None,reason=reason,role=curation.get('roles',{}).get(family,'unspecified')))
        except Exception as e:
            rows.append(dict(path=rel,sha256=sha,face_index=0,family=path.stem,style='unknown',cluster=path.stem,
                             weight=400,width=5,italic=False,eligible=False,reason='read error: '+str(e)))
    if not rows: raise ValueError('No OTF/TTF fonts found')
    m=finalize_rows(rows,curation); m['root']=str(Path(root).resolve()); return m

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['inventory'])
    p.add_argument('--root',type=Path,required=True); p.add_argument('--curation',type=Path)
    p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    c=json.loads(a.curation.read_text()) if a.curation else {}
    m=build_manifest(a.root,c); validate_manifest(m); atomic_json(a.out,m)
    print(json.dumps({'fonts':len(m['fonts']),'eligible':sum(r['eligible'] for r in m['fonts']),
        'clusters':len({r['cluster'] for r in m['fonts']}),
        'fitting_styles':dict(Counter(r['split'] for r in m['fonts'] if r['fit_selected'])),
        'excluded':dict(Counter(r['reason'] for r in m['fonts'] if not r['eligible'])),
        'digest':m['digest']},indent=2))
if __name__=='__main__': main()
