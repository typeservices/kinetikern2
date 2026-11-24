import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kk3_fontz_paths import observation_path,stable_index

class PathsTests(unittest.TestCase):
    def test_relocation_prefers_current_run(self):
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder); (data/'observations').mkdir()
            target=data/'observations/abc.json';target.write_text('{}')
            self.assertEqual(observation_path(data,'/gone/old/abc.json'),target)
            with self.assertRaises(FileNotFoundError):
                observation_path(data,'/gone/old/missing.json')
    def test_resume_identity_ignores_path_and_cached_flag(self):
        a={'records':[{'path':'a.otf','observation':'/old/abc.json','cached':True}]}
        b={'records':[{'path':'a.otf','observation':'/new/abc.json'}]}
        self.assertEqual(stable_index(a),stable_index(b))
