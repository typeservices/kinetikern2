"""Profile validation/import checks, independent of Glyphs and AppKit."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

RESOURCES = Path(__file__).resolve().parents[1] / 'plugin/Kinetikern3.glyphsPlugin/Contents/Resources'
spec = importlib.util.spec_from_file_location('fontz_profiles_test', RESOURCES / 'kk3_harness_profiles.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)
IDENTITY = {'sha256': 'a' * 64, 'punctuation_sha256': 'b' * 64}


def profile():
    core = json.loads((RESOURCES / 'kk3_harness.json').read_text())['glyphs'][:66]
    return {'format': 'kinetikern3-harness/2', 'name': 'Fontz', 'glyphs': core,
            'provenance': {'engine_sha256': IDENTITY['sha256'],
                           'punctuation_sha256': IDENTITY['punctuation_sha256'],
                           'convention': 'text', 'punctuation': True, 'status': 'experimental'},
            'stem_ref': 80, 'stem_range': [10, 250], 'looseness_range': [-1, 1],
            'reference': {'families': 2, 'observations': 3},
            'left': {k: [1, 2, 3, 4] for k in core},
            'right': {k: [5, 6, 7, 8] for k in core}, 'pairs': {'A V': -10}}


class ProfilesTest(unittest.TestCase):
    def test_original_core_subset_is_supported(self):
        self.assertEqual(len(hp.validate_profile(profile(), IDENTITY)['glyphs']), 66)

    def test_exact_runtime_identity_and_contract(self):
        changes = [('format', 'kinetikern2-harness/2'), ('name', 'Other'),
                   ('engine_sha256', 'c' * 64), ('punctuation_sha256', 'd' * 64),
                   ('convention', 'display'), ('punctuation', False), ('status', 'unknown')]
        for key, value in changes:
            with self.subTest(key=key):
                data = profile()
                (data if key in ('format', 'name') else data['provenance'])[key] = value
                with self.assertRaises(ValueError):
                    hp.validate_profile(data, IDENTITY)
        for key in ('engine_sha256', 'punctuation_sha256', 'convention', 'punctuation', 'status'):
            data = profile()
            del data['provenance'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                hp.validate_profile(data, IDENTITY)

    def test_malformed_coefficients_and_unknown_glyphs(self):
        for value in (None, True, '2', float('nan'), float('inf'), -float('inf'), 1001, 10 ** 1000):
            data = profile()
            data['left']['A'][0] = value
            with self.subTest(coefficient=value), self.assertRaises(ValueError):
                hp.validate_profile(data, IDENTITY)
        for edit in (lambda d: d['right'].pop('A'),
                     lambda d: d['left'].update(A=[1, 2, 3]),
                     lambda d: d['pairs'].update({'A percent': 3}),
                     lambda d: d['glyphs'].append('A'),
                     lambda d: d.update(categories={'Display': {}}),
                     lambda d: d.update(stem_range=[0, 100])):
            data = profile()
            edit(data)
            with self.assertRaises(ValueError):
                hp.validate_profile(data, IDENTITY)

    def test_atomic_import_validation_and_local_precedence(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(hp, 'engine_identity', return_value=IDENTITY):
            source = Path(folder) / 'source.json'
            dest = Path(folder) / 'local'
            source.write_text(json.dumps(profile()))
            target = Path(hp.import_profile(source, dest))
            self.assertEqual(target.name, 'fontz-harness.json')
            self.assertEqual(hp.load_fontz_profile(dest), profile())
            before = target.read_bytes()
            bad = profile()
            bad['provenance']['engine_sha256'] = 'wrong'
            source.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                hp.import_profile(source, dest)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(list(dest.iterdir()), [target])

    def test_profile_digest_tracks_coefficients(self):
        data = profile()
        changed = copy.deepcopy(data)
        changed['left']['A'][0] += 1
        self.assertNotEqual(hp.profile_digest(data), hp.profile_digest(changed))


if __name__ == '__main__':
    unittest.main()
