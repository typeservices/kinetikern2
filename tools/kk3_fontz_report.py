"""Private HTML and outline proofs; no font data is sent to a server."""
import argparse
import html
import json
from pathlib import Path
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from kk3_fontz_paths import observation_path
from kk3_fontz_fit import predict_applied

def esc(value):return html.escape(str(value),quote=True)

def summary_html(evaluation):
    test=evaluation['test'];gate=evaluation['gate'];status='Passed numerical gates' if gate['pass'] else 'Experimental — quality gates not passed'
    body=['<!doctype html><meta charset="utf-8"><title>Fontz harness review</title>',
          '<style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 24px;color:#222;background:#faf9f6}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{text-align:left;padding:9px;border-bottom:1px solid #ddd}small{color:#555}svg{width:100%;height:auto}details{margin:20px 0}</style>',
          '<h1>Fontz Designer Harness for Kinetikern3</h1><h2>'+status+'</h2>',
          '<p>The exported profile remains experimental pending visual review. Original means Kinetikern3 with text punctuation conventions enabled and its harness off. Comparisons use the same 66-glyph core; full-font behavior may differ. Matched errors subtract the same baseline-derived global offset from all three modes; fixed-zero errors do not.</p>',
          '<p>Local review · previously used holdout, not a fresh blind test. %d fonts across %d families. Each family has equal weight. Lower gap error is better; units per 1000 em.</p>'%(test['fonts'],test['families']),
          '<p>'+esc('; '.join(gate['reasons']) or 'All predeclared numerical checks passed. Visual review is still required.')+'</p>']
    for key,title in [('matched','Reference-matched looseness'),('fixed','Every font at Looseness 0')]:
        r=test[key];body.append('<h2>'+title+'</h2><table><tr><th>Mode</th><th>All pairs</th><th>Letters</th><th>Punctuation</th><th>90th percentile family</th></tr>')
        for mode in ('Original','Google Fonts','Fontz'):
            m=r[mode];body.append('<tr><td>'+mode+'</td>'+''.join('<td>'+('—' if m[k] is None else '%.2f'%m[k])+'</td>' for k in ('overall','letters','punctuation','p90'))+'</tr>')
        body.append('</table><p>Fontz input clamping: %d of %d fonts.</p><p>Fontz improvement versus Original: %.2f%%; 95%% family-bootstrap interval %.2f%% to %.2f%%.</p>'%(r['Fontz'].get('clamped_fonts',0),test['fonts'],r['improvement_percent'],*r['improvement_ci95']))
    r=test['matched'];body.append('<details><summary>Per-family matched errors</summary><table><tr><th>Family</th><th>Original</th><th>Google Fonts</th><th>Fontz</th></tr>')
    for f in sorted(r['Original']['families']):
        body.append('<tr><td>'+esc(f)+'</td>'+''.join('<td>%.2f</td>'%r[m]['families'][f]['overall'] for m in ('Original','Google Fonts','Fontz'))+'</tr>')
    body.append('</table></details><details><summary>Excluded fonts (%d)</summary><table>'%len(evaluation['exclusions']))
    for row in evaluation['exclusions']:body.append('<tr><td>'+esc(row['path'])+'</td><td>'+esc(row['exclusion'])+'</td></tr>')
    body.append('</table></details>')
    return ''.join(body)

def pair_svg(o,table,bundled,root,i,j):
    with TTFont(Path(root)/o['path']) as font:
        gs=font.getGlyphSet();paths=[];bounds=[]
        for k in (i,j):
            name=o['mapping'][k];rec=DecomposingRecordingPen(gs);gs[name].draw(rec)
            pen=SVGPathPen(gs);rec.replay(pen);paths.append(pen.getCommands())
            bp=BoundsPen(gs);gs[name].draw(bp);bounds.append(bp.bounds)
    target=np.asarray(o['target']);base=np.asarray(o['fixed_model']);g=predict_applied(bundled,0,o['stem'],o['runtime_baselines']['fixed']);f=predict_applied(table,0,o['stem'],o['runtime_baselines']['fixed'])
    columns=[('Designer',target[i,j]),('Original',base[i,j]),('Google Fonts',base[i,j]+g[i,j]),('Fontz',base[i,j]+f[i,j])]
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1160 180"><rect width="1160" height="180" fill="white"/>']
    upm=o['upm'];scale=65/upm;width=bounds[0][2]-bounds[0][0]
    for col,(label,gap) in enumerate(columns):
        parts.append('<text x="%d" y="25" font-family="sans-serif" font-size="14">%s · %.1f</text>'%(col*290+12,label,gap))
        parts.append('<g transform="translate(%d 135) scale(%g -%g)">'%(col*290+25,scale,scale))
        for d,x in zip(paths,[-bounds[0][0],width+gap*upm/1000-bounds[1][0]]):parts.append('<path d="%s" transform="translate(%g 0)"/>'%(esc(d),x))
        parts.append('</g>')
    parts.append('</svg>');return ''.join(parts)

def write_report(evaluation,output_dir):
    out=Path(output_dir);body=summary_html(evaluation)
    manifest=json.loads((out/'manifest.json').read_text());table=json.loads((out/'fontz-harness.json').read_text())
    BUNDLED=json.loads((out/'google-fonts-comparison.json').read_text())
    from kk3_fontz_evaluate import export_profile, validate_frozen_candidate
    from kk3_fontz_corpus import digest_json
    candidate=json.loads((out/'candidate.json').read_text())
    validate_frozen_candidate(candidate)
    if digest_json(BUNDLED)!=candidate['comparison_digest']:
        raise ValueError('Proof comparison differs from frozen evaluation')
    lock=json.loads((out/'evaluation-lock.json').read_text())
    if digest_json(evaluation)!=lock['digest'] or evaluation['candidate_digest']!=candidate['table_digest']:
        raise ValueError('Frozen evaluation changed')
    if table!=export_profile(candidate['table'],evaluation):
        raise ValueError('Proof profile differs from evaluated candidate')
    index=json.loads((out/'data/index.json').read_text());obs=[json.loads(observation_path(out/'data',r['observation']).read_text()) for r in index['records'] if r.get('split')=='test' and 'observation' in r]
    # Show gains/regressions and the coverage extremes independently of acceptance.
    ranked=[]
    for o in obs:
        e=np.asarray(o['target'])-np.asarray(o['fixed_model']);c=predict_applied(table,0,o['stem'],o['runtime_baselines']['fixed'])
        improvement=np.abs(e)-np.abs(e-c)
        for kind,flat in [('Largest gain',np.argmax(improvement)),('Largest regression',np.argmin(improvement))]:
            i,j=np.unravel_index(flat,e.shape);ranked.append((float(improvement[i,j]),kind,o,int(i),int(j)))
    chosen=sorted([r for r in ranked if r[1]=='Largest gain'],reverse=True,key=lambda r:r[0])[:3]+sorted([r for r in ranked if r[1]=='Largest regression'],key=lambda r:r[0])[:3]
    if obs:
        for title,fn in [('Lightest stem',lambda o:o['stem']),('Heaviest stem',lambda o:-o['stem']),('Tightest reference',lambda o:o['looseness']),('Loosest reference',lambda o:-o['looseness'])]:
            o=min(obs,key=fn);i=o['glyphs'].index('parenleft');j=o['glyphs'].index('A');chosen.append((0,title,o,i,j))
    body+='<h2>Outline proofs at Looseness 0</h2><p>Actual pair gaps, without subtracting a global offset. These proofs contain local font outlines; keep this report private.</p>'
    for delta,title,o,i,j in chosen:
        body+='<h3>'+esc(title+' — '+o['path']+' — '+o['glyphs'][i]+' '+o['glyphs'][j])+'</h3>'+pair_svg(o,table,BUNDLED,manifest['root'],i,j)
    target=out/'report.html';target.write_text(body,encoding='utf-8');return target

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    print(write_report(json.loads((a.run/'evaluation.json').read_text()),a.run))
