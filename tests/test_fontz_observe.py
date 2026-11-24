import sys,unittest,tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kk3_fontz_observe import validate_case, normalized_gaps, match_looseness, observation_identity
class ObserveTests(unittest.TestCase):
 def test_known_gaps_and_upm(self):
  c={'upm':1000,'pairs':[{'left':0,'right':0,'gap':20},{'left':0,'right':1,'gap':180},{'left':1,'right':0,'gap':100},{'left':1,'right':1,'gap':100}]}
  self.assertEqual(normalized_gaps(c).tolist(),[[20,180],[100,100]])
  c['upm']=2000
  for p in c['pairs']:p['gap']*=2
  self.assertEqual(normalized_gaps(c).tolist(),[[20,180],[100,100]])
 def test_missing_or_substituted_pairs_rejected(self):
  for c in ({'characters':['A'],'pairs':[],'skipped':[]},{'characters':['A','V'],'pairs':[{}]*3,'skipped':[{}]}):
   with self.assertRaises(ValueError):validate_case(c,'AV')
 def test_matching_recovers_known_looseness(self):
  target=np.array([[101.234,101.234],[101.234,101.234]])
  L,m=match_looseness(target,lambda x:np.full((2,2),100+10*x))
  self.assertAlmostEqual(L,.1234,places=3)
 def test_identity_changes_with_engine_and_font(self):
  a=observation_identity({'sha256':'a'},{'engine':'one'})
  self.assertNotEqual(a,observation_identity({'sha256':'b'},{'engine':'one'}))
  self.assertNotEqual(a,observation_identity({'sha256':'a'},{'engine':'two'}))
 def test_cached_observation_rejects_changed_source_font(self):
  import hashlib,json
  from kk3_fontz_observe import _worker
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);font=root/'f.otf';font.write_bytes(b'original')
   row={'root':d,'path':'f.otf','sha256':hashlib.sha256(b'original').hexdigest(),'cluster':'F','split':'tuning'}
   settings={'engine':'one'};identity=observation_identity(row,settings)
   (root/(identity+'.json')).write_text(json.dumps({'identity':identity}))
   self.assertTrue(_worker((row,settings,d))['cached'])
   font.write_bytes(b'changed')
   with self.assertRaises(ValueError):_worker((row,settings,d))
