#!/usr/bin/env python3
"""Extract supported horizontal Latin pair gaps, including placement offsets."""
import hashlib
import json
from pathlib import Path
import fontTools
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb
from kk3_fontz_corpus import atomic_json, digest_json
import kk3_fonts as kf
from kk3_fonts import CHARS, tt_contours, pen_contours, rhythm_group

EXTRACTOR_VERSION=2

class UnsupportedReference(ValueError):
    """A known unsupported case, distinct from corrupt or missing frozen data."""


SHAPING={'direction':'ltr','script':'Latn','language':'und','liga':False,'clig':False,'dlig':False}

def context_key(path,chars,face_index=0):
    return dict(font_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),chars=chars,face_index=face_index,
                extractor=EXTRACTOR_VERSION,source_sha256=digest_json({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (Path(__file__),Path(kf.__file__),Path(kf.kb.__file__))}),fonttools=fontTools.__version__,harfbuzz=hb.__version__,shaping=SHAPING)

def _contextual_kern(f):
    if 'GPOS' not in f: return False
    g=f['GPOS'].table
    if not g.FeatureList or not g.LookupList: return False
    indices={i for r in g.FeatureList.FeatureRecord if r.FeatureTag=='kern' for i in r.Feature.LookupListIndex}
    for i in indices:
        lookup=g.LookupList.Lookup[i]
        types=[lookup.LookupType] if lookup.LookupType!=9 else [s.ExtensionLookupType for s in lookup.SubTable]
        if any(t not in (1,2) for t in types): return True
    return False

def extract_case(path: Path, face_index: int=0, chars: str=CHARS) -> dict:
    path=Path(path); key=context_key(path,chars,face_index)
    with TTFont(path,fontNumber=face_index) as f:
        if 'fvar' in f: raise UnsupportedReference('variable font requires an explicit static instance; deferred in v1')
        if _contextual_kern(f): raise UnsupportedReference('contextual kern lookup unsupported in pair-only calibration')
        upm=f['head'].unitsPerEm; glyphset=f.getGlyphSet(); cmap=f.getBestCmap() or {}
        chars=''.join(dict.fromkeys(ch for ch in chars if ord(ch) in cmap))
        names=[]; selected=[]; bounds=[]; contours=[]; advances=[]; groups=[]
        for ch in chars:
            name=cmap[ord(ch)]
            if name in names: continue
            pen=BoundsPen(glyphset); glyphset[name].draw(pen)
            if pen.bounds is None: continue
            names.append(name); selected.append(ch); bounds.append(list(pen.bounds))
            contours.append(tt_contours(f,name) if 'glyf' in f else pen_contours(f,name))
            advances.append(f['hmtx'][name][0]); groups.append(rhythm_group(ch))
        if len(names)<2: raise UnsupportedReference('insufficient nonempty glyphs')
        font=hb.Font(hb.Face(path.read_bytes(),face_index)); font.scale=(upm,upm)
        gids=[f.getGlyphID(n) for n in names]
        def shape(text,kern):
            b=hb.Buffer(); b.add_str(text); b.direction='ltr'; b.script='Latn'; b.language='und'
            hb.shape(font,b,{'kern':kern,'liga':False,'clig':False,'dlig':False})
            return [(i.codepoint,p.x_advance,p.x_offset,p.y_advance,p.y_offset) for i,p in zip(b.glyph_infos,b.glyph_positions)]
        pairs=[]; skipped=[]
        for i,a in enumerate(selected):
            for j,b in enumerate(selected):
                text=a+b; off=shape(text,False); on=shape(text,True); expected=[gids[i],gids[j]]
                reason=None
                if [g[0] for g in off]!=expected or [g[0] for g in on]!=expected: reason='substitution or reordered glyphs'
                elif any(p[3] or p[4] for p in off+on): reason='vertical positioning'
                elif off!=[(gids[i],advances[i],0,0,0),(gids[j],advances[j],0,0,0)]: reason='non-kern contextual positioning'
                if reason:
                    skipped.append({'text':text,'reason':reason}); continue
                # The second ink's left edge minus the first ink's right edge.
                gap=on[0][1]+on[1][2]+bounds[j][0]-(on[0][2]+bounds[i][2])
                nominal=advances[i]-bounds[i][2]+bounds[j][0]
                pairs.append({'left':i,'right':j,'text':text,'gap':gap,'adjustment':gap-nominal})
        return dict(schema=1,**key,upm=upm,names=names,characters=selected,contours=contours,bounds=bounds,
                    advances=advances,lsb=[b[0] for b in bounds],rsb=[a-b[2] for a,b in zip(advances,bounds)],
                    groups=groups,pairs=pairs,skipped=skipped)

def load_case(cache_path: Path) -> dict:
    case=json.loads(Path(cache_path).read_text())
    if case.get('schema')!=1 or case.get('extractor')!=EXTRACTOR_VERSION: raise ValueError('Unsupported cached case')
    return case

def cached_case(path: Path, cache: Path, chars: str=CHARS, expected_sha=None) -> dict:
    key=context_key(path,chars)
    if expected_sha and key['font_sha256']!=expected_sha: raise ValueError('Font changed since manifest freeze: '+str(path))
    target=Path(cache)/(digest_json(key)+'.json')
    if target.exists():
        c=load_case(target)
        if any(c.get(k)!=v for k,v in key.items()): raise ValueError('Cache identity mismatch')
        return c
    c=extract_case(path,0,chars); atomic_json(target,c); return c
