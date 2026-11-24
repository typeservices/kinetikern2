"""Freeze validation-selected harnesses before opening the previously used holdout."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from kk3_fontz_corpus import digest_json,atomic_json
from kk3_fontz_paths import observation_path, stable_index
from kk3_fontz_fit import fit_harness,predict_applied,project_table

def evaluate_modes(observations,tables):
    if not observations:raise ValueError('No observations to evaluate')
    names=observations[0]['glyphs'];letters=np.array([len(n)==1 and n.isalpha() for n in names])
    lm=letters[:,None]&letters[None,:];pm=~lm
    report={'fonts':len(observations),'families':len({o['cluster'] for o in observations})}
    for setting in ('matched','fixed'):
        modes={}
        for mode,table in [('Original',None)]+list(tables.items()):
            if table is not None and table['glyphs']!=names:raise ValueError('Glyph order mismatch')
            by_family=defaultdict(list);font_rows=[];clamped=0
            for o in observations:
                if o['glyphs']!=names:raise ValueError('Mixed glyph order')
                model=np.asarray(o['model'] if setting=='matched' else o['fixed_model'])
                target=np.asarray(o['target']);L=o['looseness'] if setting=='matched' else 0
                if table is not None and (not table['looseness_range'][0]<=L<=table['looseness_range'][1] or not table['stem_range'][0]<=o['stem']<=table['stem_range'][1]):clamped+=1
                correction=predict_applied(table,L,o['stem'],o.get('runtime_baselines',{}).get(setting)) if table is not None else np.zeros_like(model)
                error=np.abs(target-model-correction-(o['offset'] if setting=='matched' else 0))
                if not np.isfinite(error).all():raise ValueError('Nonfinite evaluation')
                vals={'overall':float(error.mean()),'letters':float(error[lm].mean()) if lm.any() else None,
                      'punctuation':float(error[pm].mean()) if pm.any() else None}
                by_family[o['cluster']].append(vals);font_rows.append(dict(path=o['path'],cluster=o['cluster'],**vals))
            families={f:{key:float(np.mean([r[key] for r in rows])) if all(r[key] is not None for r in rows) else None
                         for key in ('overall','letters','punctuation')} for f,rows in by_family.items()}
            means={key:float(np.mean([r[key] for r in families.values()])) if all(r[key] is not None for r in families.values()) else None
                   for key in ('overall','letters','punctuation')}
            modes[mode]=dict(**means,clamped_fonts=clamped,p90=float(np.percentile([r['overall'] for r in families.values()],90)),families=families,fonts=font_rows)
        keys=sorted(modes['Original']['families']);base=np.array([modes['Original']['families'][f]['overall'] for f in keys])
        candidate=np.array([modes['Fontz']['families'][f]['overall'] for f in keys]);rng=np.random.default_rng(20261009)
        ix=rng.integers(0,len(keys),size=(2000,len(keys)));den=base[ix].mean(axis=1)
        improvement=100*(den-candidate[ix].mean(axis=1))/np.maximum(den,1e-12)
        modes['improvement_percent']=100*(base.mean()-candidate.mean())/max(base.mean(),1e-12)
        modes['improvement_ci95']=[float(x) for x in np.percentile(improvement,[2.5,97.5])]
        report[setting]=modes
    return report

def promotion_gate(report):
    r=report['matched'];a=r['Original'];b=r['Fontz'];reasons=[]
    if report['families']<5:reasons.append('Fewer than five evaluation families')
    if b['overall']>a['overall']*.95:reasons.append('Below 5% improvement versus Original')
    if b['overall']>r['Google Fonts']['overall']:reasons.append('Worse than bundled Google Fonts harness')
    for key in ('letters','punctuation'):
        if a[key] is None or b[key] is None or b[key]>a[key]*1.02:reasons.append(key+' regressed over 2% or unavailable')
    if b['p90']>a['p90']:reasons.append('90th-percentile family error regressed')
    if r['improvement_ci95'][0]<=0:reasons.append('Improvement is statistically inconclusive')
    return {'pass':not reasons,'reasons':reasons}

def load_observations(index, manifest, data_dir=None):
    records=index['records'];expected={r['path']:r for r in manifest['fonts']}
    if (index['manifest']!=manifest['digest'] or len(records)!=len(expected)
            or len({r['path'] for r in records})!=len(records)
            or {r['path'] for r in records}!=set(expected)):
        raise ValueError('Incomplete, duplicated or changed observation manifest')
    by_split={s:[] for s in ('tuning','validation','test')}
    for record in records:
        row=expected[record['path']]
        if any(record[k]!=row[k] for k in ('cluster','split')):
            raise ValueError('Index partition changed')
        if 'observation' not in record:
            if not record.get('exclusion'):raise ValueError('Missing exclusion reason')
            continue
        if not row['selected']:raise ValueError('Unapproved reference observation')
        path=observation_path(data_dir,record['observation']) if data_dir is not None else Path(record['observation'])
        o=json.loads(path.read_text())
        if any(o[k]!=row[k] for k in ('path','sha256','cluster','split')):
            raise ValueError('Observation identity or partition changed')
        if digest_json(o['protocol'])!=index['protocol']:raise ValueError('Mixed observation protocol')
        by_split[row['split']].append(o)
    return by_split

def validate_frozen_candidate(candidate):
    if digest_json(candidate['table']) != candidate['table_digest']:
        raise ValueError('Frozen candidate coefficients changed')

def export_profile(table,evaluation):
    shipped=json.loads(json.dumps(table));shipped['provenance']['evaluation_digest']=digest_json(evaluation)
    shipped['provenance']['status']='experimental'
    shipped['provenance']['numerical_gates_passed']=bool(evaluation['gate']['pass'])
    shipped['provenance']['visual_review']='pending'
    return shipped


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--bundled',type=Path,required=True)
    a=p.parse_args();index=json.loads((a.data/'index.json').read_text());records=index['records']
    manifest=json.loads((a.out/'manifest.json').read_text())
    by_split=load_observations(index,manifest,a.data)
    tables={'Google Fonts':project_table(json.loads(a.bundled.read_text()), by_split['tuning'][0]['glyphs'])}
    enrichment=json.loads((a.out/'runtime-enrichment.json').read_text())
    if any(o.get('runtime_identity')!=enrichment or not o.get('runtime_baselines') for rows in by_split.values() for o in rows):
        raise ValueError('Runtime baseline enrichment is incomplete or inconsistent')
    identity=digest_json({'numpy_version':np.__version__,'index':stable_index(index),'observations':{split:[digest_json(o) for o in rows] for split,rows in by_split.items()},'bundled':tables['Google Fonts'],'sources':{
        path.name:__import__('hashlib').sha256(path.read_bytes()).hexdigest() for path in (Path(__file__),Path(__file__).with_name('kk3_fontz_fit.py'))}})
    comparison=a.out/'google-fonts-comparison.json'
    if comparison.exists() and json.loads(comparison.read_text()) != tables['Google Fonts']:
        raise ValueError('Frozen comparison table changed')
    atomic_json(comparison,tables['Google Fonts'])
    frozen=a.out/'candidate.json'
    if frozen.exists():
        candidate=json.loads(frozen.read_text())
        if candidate['run_identity']!=identity:raise ValueError('Frozen run identity changed; use a new reviewed run')
    else:
        scores=[]
        for model in ('constant','features'):
            for shrink in (.25,.5,1.):
                t=fit_harness(by_split['tuning'],{'model':model,'shrinkage':shrink})
                report=evaluate_modes(by_split['validation'],dict(tables,Fontz=t));score=report['matched']['Fontz']['overall']
                scores.append((score,t,report));print(model,shrink,score,flush=True)
        _,t,validation=min(scores,key=lambda row:row[0]);t['provenance']['validation_digest']=digest_json(sorted(o['identity'] for o in by_split['validation']))
        candidate={'run_identity':identity,'comparison_digest':digest_json(tables['Google Fonts']),'table':t,'table_digest':digest_json(t),'validation':validation,
                   'search':[{'fit':s[1]['fit'],'score':s[0]} for s in scores]}
        atomic_json(frozen,candidate)
    validate_frozen_candidate(candidate)
    t=candidate['table'];test_path=a.out/'evaluation.json'
    if test_path.exists():
        final=json.loads(test_path.read_text())
        lock=json.loads((a.out/'evaluation-lock.json').read_text())
        if digest_json(final)!=lock['digest']:raise ValueError('Frozen evaluation changed')
        if final['run_identity']!=identity or final['candidate_digest']!=candidate['table_digest']:raise ValueError('Evaluation identity mismatch')
    else:
        report=evaluate_modes(by_split['test'],dict(tables,Fontz=t))
        final={'run_identity':identity,'candidate_digest':candidate['table_digest'],'test':report,'gate':promotion_gate(report),
               'holdout_note':'Previously used holdout; not an independent blind test','exclusions':[r for r in records if 'exclusion' in r]}
        atomic_json(test_path,final)
        atomic_json(a.out/'evaluation-lock.json',{'digest':digest_json(final),'candidate_digest':candidate['table_digest']})
    shipped=export_profile(t,final)
    atomic_json(a.out/'fontz-harness.json',shipped)
    print(json.dumps(final['gate']),flush=True)
if __name__=='__main__':main()
