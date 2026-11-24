import sys,unittest,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kk3_fontz_fit import fit_harness,predict_corrections
class FitTests(unittest.TestCase):
 def obs(self):
  return [dict(cluster=str(i),split='tuning',glyphs=['A','V'],looseness=0,stem=85,residual=[[0,10],[-10,0]],identity=str(i),protocol={'engine':'test','punctuation_sha256':'test'}) for i in range(10)]
 def test_constant_recovery_and_singular_fallback(self):
  t=fit_harness(self.obs(),{'model':'features','shrinkage':1})
  self.assertEqual(t['fit']['model'],'constant')
  np.testing.assert_allclose(predict_corrections(t,0,85),[[0,10],[-10,0]],atol=.01)
 def test_duplicates_do_not_change_family_weight(self):
  obs=self.obs();obs[0]['residual']=[[0,20],[-20,0]]
  a=fit_harness(obs,{'model':'constant','shrinkage':1})
  b=fit_harness(obs+[copy.deepcopy(obs[0]) for _ in range(20)],{'model':'constant','shrinkage':1})
  np.testing.assert_allclose(predict_corrections(a,0,85),predict_corrections(b,0,85),atol=.001)
 def test_no_holdout_or_nonfinite(self):
  obs=self.obs();obs[0]['split']='test'
  with self.assertRaises(ValueError):fit_harness(obs,{})
  obs=self.obs();obs[0]['residual'][0][0]=float('nan')
  with self.assertRaises(ValueError):fit_harness(obs,{})
 def test_minimum_families(self):
  with self.assertRaises(ValueError):fit_harness(self.obs()[:9],{})
 def test_runtime_threshold_preserves_sides_and_existing_exceptions(self):
  from kk3_fontz_fit import predict_applied
  t={'glyphs':['A','V'],'stem_ref':85,'stem_range':[85,85],'looseness_range':[0,0],
     'left':{'A':[1,0,0,0],'V':[1,0,0,0]},'right':{'A':[1,0,0,0],'V':[1,0,0,0]},
     'pairs':{'A A':3,'A V':3,'V A':3}}
  b={'kerning':[[0,0],[-10,0]],'explicit':[[False,True],[False,False]]}
  np.testing.assert_allclose(predict_applied(t,0,85,b),[[2,5],[5,2]])
