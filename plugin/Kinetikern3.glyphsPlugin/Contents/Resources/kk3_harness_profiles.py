"""Validated local Fontz harness profiles. Standard library only."""
import hashlib
import json
import math
import os
import tempfile
from functools import lru_cache

RESOURCES=os.path.dirname(os.path.abspath(__file__))
@lru_cache(maxsize=1)
def engine_identity():
    with open(os.path.join(RESOURCES,'libkinetikern3.dylib'),'rb') as f:
        engine_hash = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(RESOURCES, 'kk3_punctuation.json'), 'rb') as f:
        punctuation_hash = hashlib.sha256(f.read()).hexdigest()
    return {'sha256': engine_hash, 'punctuation_sha256': punctuation_hash}

def profile_digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def profile_directory():
    return os.path.expanduser('~/Library/Application Support/Kinetikern3/Harnesses')

def _read(path):
    if os.path.getsize(path)>1024*1024:raise ValueError('Harness profile exceeds 1 MB')
    with open(path,encoding='utf-8') as f:return json.load(f)

def validate_profile(data,identity):
    if not isinstance(data,dict) or data.get('format')!='kinetikern3-harness/2':raise ValueError('Unsupported Fontz harness format')
    if data.get('name') != 'Fontz':raise ValueError('Expected the Fontz harness')
    provenance=data.get('provenance',{})
    if not isinstance(provenance,dict):raise ValueError('Invalid provenance')
    if provenance.get('engine_sha256')!=identity['sha256']:raise ValueError('Fontz harness belongs to a different engine build')
    if provenance.get('punctuation_sha256') != identity['punctuation_sha256']:raise ValueError('Fontz harness belongs to different punctuation conventions')
    if provenance.get('convention') != 'text':raise ValueError('Fontz requires text conventions')
    if provenance.get('punctuation') is not True:raise ValueError('Fontz requires punctuation enabled')
    if data.get('categories'):raise ValueError('Fontz does not support category overlays')
    if provenance.get('status') not in ('experimental','passed'):raise ValueError('Missing harness evaluation status')
    core=_read(os.path.join(RESOURCES,'kk3_harness.json'))['glyphs']
    glyphs = data.get('glyphs')
    if (not isinstance(glyphs, list) or not glyphs or any(not isinstance(k, str) for k in glyphs)
            or len(set(glyphs)) != len(glyphs) or glyphs != [k for k in core if k in glyphs]):
        raise ValueError('Unexpected harness glyph order or unsupported core glyph')
    core = glyphs
    def number(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError('Nonfinite or invalid coefficient')
        try:
            value = float(v)
        except (OverflowError, ValueError):
            raise ValueError('Nonfinite or invalid coefficient')
        if not math.isfinite(value):
            raise ValueError('Nonfinite or invalid coefficient')
        return value
    if number(data.get('stem_ref'))<=0:raise ValueError('Invalid reference stem')
    for key in ('stem_range','looseness_range'):
        values=data.get(key)
        if not isinstance(values,list) or len(values)!=2:raise ValueError('Invalid harness range')
        low,high=map(number,values)
        if low>high or (key=='stem_range' and low<=0):raise ValueError('Invalid harness range')
    for side in ('left','right'):
        values=data.get(side)
        if not isinstance(values,dict) or set(values)!=set(core):raise ValueError('Incomplete side coefficients')
        for coef in values.values():
            if not isinstance(coef,list) or len(coef)!=4:raise ValueError('Expected four side coefficients')
            if any(abs(number(v))>1000 for v in coef):raise ValueError('Side coefficient outside supported range')
    pairs=data.get('pairs')
    if not isinstance(pairs,dict):raise ValueError('Invalid pair coefficients')
    for key,value in pairs.items():
        if not isinstance(key,str) or len(key.split(' '))!=2 or any(n not in core for n in key.split(' ')):raise ValueError('Unknown pair glyph')
        if abs(number(value))>1000:raise ValueError('Pair correction outside supported range')
    ref=data.get('reference',{})
    if not isinstance(ref,dict):raise ValueError('Invalid reference counts')
    for key in ('families','observations'):
        if isinstance(ref.get(key),bool) or not isinstance(ref.get(key),int) or ref[key]<1:raise ValueError('Invalid reference counts')
    profile_digest(data)
    return data

def load_fontz_profile(directory=None):
    path=os.path.join(str(directory or profile_directory()),'fontz-harness.json')
    if not os.path.exists(path):path=os.path.join(RESOURCES,'fontz-harness.json')
    if not os.path.exists(path):return None
    return validate_profile(_read(path),engine_identity())

def available_profiles():
    return [_read(os.path.join(RESOURCES,'kk3_harness.json')),load_fontz_profile()]

def import_profile(path,directory=None):
    data=validate_profile(_read(path),engine_identity());folder=str(directory or profile_directory())
    os.makedirs(folder,exist_ok=True);target=os.path.join(folder,'fontz-harness.json');tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',dir=folder,delete=False,encoding='utf-8') as f:
            tmp=f.name;json.dump(data,f,allow_nan=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,target)
    finally:
        if tmp and os.path.exists(tmp):os.unlink(tmp)
    return target
