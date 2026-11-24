import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kk3_fontz_evaluate import evaluate_modes,promotion_gate
class EvaluateTests(unittest.TestCase):
 def obs(self):
  return [dict(path=str(i),cluster=str(i),glyphs=['A','period'],stem=85,looseness=0,target=[[10,10],[10,10]],model=[[0,0],[0,0]],fixed_model=[[0,0],[0,0]],offset=0) for i in range(10)]
 def table(self,v):
  return dict(glyphs=['A','period'],stem_ref=85,stem_range=[85,85],looseness_range=[0,0],left={n:[v/2,0,0,0] for n in ['A','period']},right={n:[v/2,0,0,0] for n in ['A','period']},pairs={})
 def test_identical_inputs_and_family_weighting(self):
  o=self.obs();o[0]['target']=[[30,30],[30,30]]
  a=evaluate_modes(o,{'Google Fonts':self.table(5),'Fontz':self.table(8)})
  b=evaluate_modes(o+[copy.deepcopy(o[0])]*3,{'Google Fonts':self.table(5),'Fontz':self.table(8)})
  # Repeat every observation equally, then add exact family duplicates separately.
  c=evaluate_modes(o+[copy.deepcopy(o[0]) for _ in range(20)],{'Google Fonts':self.table(5),'Fontz':self.table(8)})
  self.assertAlmostEqual(a['matched']['Original']['overall'],c['matched']['Original']['overall'])
  self.assertEqual(a['matched']['Fontz']['overall'],4)
 def test_gates_pass_and_fail(self):
  good=evaluate_modes(self.obs(),{'Google Fonts':self.table(5),'Fontz':self.table(8)})
  self.assertTrue(promotion_gate(good)['pass'])
  bad=evaluate_modes(self.obs(),{'Google Fonts':self.table(5),'Fontz':self.table(-5)})
  self.assertFalse(promotion_gate(bad)['pass'])
 def test_observation_partition_is_verified_against_manifest(self):
  import tempfile,json
  from kk3_fontz_corpus import digest_json
  from kk3_fontz_evaluate import load_observations
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'observation.json';protocol={'engine':'test','punctuation_sha256':'test'}
   row={'path':'a.otf','sha256':'abc','cluster':'A','split':'tuning','selected':True}
   obs=dict(row,protocol=protocol);p.write_text(json.dumps(obs))
   index={'manifest':'manifest','protocol':digest_json(protocol),'records':[dict(row,observation=str(p))]}
   manifest={'digest':'manifest','fonts':[row]}
   self.assertEqual(len(load_observations(index,manifest)['tuning']),1)
   obs['split']='test';p.write_text(json.dumps(obs))
   with self.assertRaises(ValueError):load_observations(index,manifest)
   obs['split']='tuning';p.write_text(json.dumps(obs));index['records']*=2
   with self.assertRaises(ValueError):load_observations(index,manifest)
 def test_reports_clamped_inputs(self):
  obs=self.obs();obs[0]['stem']=100;obs[0]['looseness']=.2
  r=evaluate_modes(obs,{'Google Fonts':self.table(5),'Fontz':self.table(8)})
  self.assertEqual(r['matched']['Fontz']['clamped_fonts'],1)
 def test_frozen_candidate_rejects_modified_coefficients(self):
  from kk3_fontz_corpus import digest_json
  from kk3_fontz_evaluate import validate_frozen_candidate
  t=self.table(5);c={'table':t,'table_digest':digest_json(t)}
  validate_frozen_candidate(c)
  t['left']['A'][0]+=1
  with self.assertRaises(ValueError):validate_frozen_candidate(c)

class ExportTests(unittest.TestCase):
 def test_numeric_pass_stays_experimental_without_visual_review(self):
  from kk3_fontz_evaluate import export_profile
  table={'provenance':{'status':'experimental'}}
  exported=export_profile(table,{'gate':{'pass':True}})
  self.assertEqual(exported['provenance']['status'],'experimental')
  self.assertTrue(exported['provenance']['numerical_gates_passed'])
  self.assertEqual(exported['provenance']['visual_review'],'pending')
  self.assertNotIn('visual_review',table['provenance'])
