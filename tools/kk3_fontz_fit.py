"""Family-balanced offline harness fitting. Never accepts held-out observations."""
from collections import Counter
import numpy as np
from kk3_fontz_corpus import digest_json

def weighted_quantile(values, weights, q=.5):
    order=np.argsort(values,kind='stable');v=np.asarray(values)[order];w=np.asarray(weights)[order]
    return float(v[min(np.searchsorted(np.cumsum(w),q*w.sum()),len(v)-1)])

def robust_fit(X,y,w):
    beta=np.linalg.lstsq(X*np.sqrt(w)[:,None],y*np.sqrt(w),rcond=None)[0]
    for _ in range(40):
        residual=y-X@beta;center=weighted_quantile(residual,w)
        scale=1.4826*weighted_quantile(np.abs(residual-center),w) or 1.
        weights=w*np.minimum(1,1.345*scale/np.maximum(np.abs(residual),1e-12))
        nxt=np.linalg.lstsq(X*np.sqrt(weights)[:,None],y*np.sqrt(weights),rcond=None)[0]
        if np.max(np.abs(nxt-beta))<1e-6:return nxt
        beta=nxt
    return beta

def decompose(matrix):
    E=matrix.copy();r=np.zeros(len(E));c=np.zeros(len(E))
    for _ in range(10):
        d=np.median(E,axis=1);r+=d;E-=d[:,None]
        d=np.median(E,axis=0);c+=d;E-=d[None,:]
    # Identifiability convention without losing the reconstructed residual.
    shift=np.median(r);r-=shift;c+=shift
    return r,c,E

def fit_harness(observations,config):
    if not observations or any(o['split']!='tuning' for o in observations):raise ValueError('Only tuning observations may be fitted')
    counts=Counter(o['cluster'] for o in observations)
    if len(counts)<10:raise ValueError('At least 10 training families required')
    names=observations[0]['glyphs'];n=len(names);engines={o['protocol']['engine'] for o in observations}
    if len(engines)!=1 or any(o['glyphs']!=names for o in observations):raise ValueError('Mixed identities or glyph order')
    matrices=np.asarray([o['residual'] for o in observations],float)
    if matrices.shape!=(len(observations),n,n) or not np.isfinite(matrices).all():raise ValueError('Invalid residual matrices')
    L=np.array([o['looseness'] for o in observations]);stem=np.array([o['stem'] for o in observations])
    if not np.isfinite(L).all() or not np.isfinite(stem).all() or np.any(stem<=0):raise ValueError('Invalid stem or looseness')
    w=np.array([1/counts[o['cluster']] for o in observations]);logstem=np.log(stem/85)
    X=np.column_stack([np.ones(len(L)),L,logstem,L*logstem]);model=config.get('model','constant')
    if model not in ('constant','features'):raise ValueError('Unknown model')
    if model=='features' and (np.linalg.matrix_rank(X*np.sqrt(w)[:,None])<4 or np.linalg.cond(X*np.sqrt(w)[:,None])>=1e6):model='constant'
    if model=='constant':X=X[:,:1]
    shrink=float(config.get('shrinkage',1))
    if shrink not in (.25,.5,1.):raise ValueError('Unsupported shrinkage')
    decomposition=[decompose(m) for m in matrices];r,c,E=map(np.array,zip(*decomposition))
    def sides(target):
        coefficients=[]
        for j in range(n):
            b=robust_fit(X,target[:,j],w)*shrink
            coefficients.append([round(float(x),6) for x in b]+[0.]*(4-len(b)))
        return dict(zip(names,coefficients))
    families=sorted(counts);family_E=np.array([np.median(E[[i for i,o in enumerate(observations) if o['cluster']==f]],axis=0) for f in families])
    med=np.median(family_E,axis=0);agreement=np.mean(np.sign(family_E)==np.sign(med)[None],axis=0)
    keep=(np.abs(med)>=3)&(agreement>=.75)&(len(families)>=8)
    pairs={names[i]+' '+names[j]:round(float(med[i,j]*shrink),6) for i,j in zip(*np.where(keep))}
    return dict(format='kinetikern3-harness/2',name='Fontz',about='Learned locally from the Fontz collection; upright Latin core.',
                stem_ref=85.,looseness_range=[weighted_quantile(L,w,.02),weighted_quantile(L,w,.98)],
                stem_range=[weighted_quantile(stem,w,.02),weighted_quantile(stem,w,.98)],glyphs=names,
                left=sides(c),right=sides(r),pairs=pairs,reference={'families':len(families),'observations':len(observations)},
                fit={'model':model,'shrinkage':shrink,'pair_min_families':8,'pair_sign_agreement':.75,'pair_min_units':3},
                provenance={'engine_sha256':next(iter(engines)),'punctuation_sha256':observations[0]['protocol']['punctuation_sha256'],
                            'convention':'text','punctuation':True,'status':'experimental',
                            'training_digest':digest_json(sorted(o['identity'] for o in observations)),
                            'holdout_note':'Previously used holdout; not an independent blind test'})

def predict_corrections(table,looseness,stem):
    L=float(np.clip(looseness,*table['looseness_range']));s=float(np.clip(stem,*table['stem_range']))
    w=np.log(s/table['stem_ref']);f=np.array([1,L,w,L*w]);names=table['glyphs']
    r=np.array([table['right'][n] for n in names])@f;c=np.array([table['left'][n] for n in names])@f
    out=r[:,None]+c[None,:];indices={n:i for i,n in enumerate(names)}
    for key,v in table['pairs'].items():
        a,b=key.split();out[indices[a],indices[b]]+=v
    return out

def predict_applied(table,looseness,stem,baseline,threshold=5):
    """Match run.rs apply_harness: only new zero-base pairs face thresholding."""
    out=predict_corrections(table,looseness,stem)
    if not table['pairs']:return out
    if baseline is None:raise ValueError('Runtime kerning baseline is required for pair corrections')
    k=np.asarray(baseline['kerning']);explicit=np.asarray(baseline['explicit'],dtype=bool)
    if k.shape!=out.shape or explicit.shape!=out.shape:raise ValueError('Runtime baseline shape mismatch')
    indices={n:i for i,n in enumerate(table['glyphs'])}
    for pair,d in table['pairs'].items():
        a,b=pair.split();i,j=indices[a],indices[b]
        if not explicit[i,j] and k[i,j]==0 and abs(d)<threshold:out[i,j]-=d
    return out


def project_table(table, names):
    """Compare the bundled 88-glyph table on the same 66-glyph Fontz core."""
    import copy
    if not set(names) <= set(table['glyphs']):
        raise ValueError('Comparison table does not cover the Fontz core')
    out = copy.deepcopy(table)
    out['glyphs'] = list(names)
    for side in ('left', 'right'):
        out[side] = {n: table[side].get(n, [0., 0., 0., 0.]) for n in names}
    out['pairs'] = {p: v for p, v in table['pairs'].items() if all(n in names for n in p.split())}
    out.pop('categories', None)
    return out
