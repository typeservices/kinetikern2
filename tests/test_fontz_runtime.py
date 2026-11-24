"""Exercise correction plans and window state transitions without Glyphs."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
from test_fontz_profiles import hp, profile, RESOURCES

bridge = types.SimpleNamespace(RULE_FIXED=1, RULE_FOLLOW_SAME=2, RULE_FOLLOW_OPPOSITE=3, NONE=65535, FEATURE_HARNESS=1, GLYPH_FIXED_ADVANCE=1, ENTRY_GLYPH_GLYPH=0, GLYPHOPT_FOLLOW_SPACING=1, GLYPHOPT_FOLLOW_KERNING=2)
spec = importlib.util.spec_from_file_location('fontz_runtime_test', RESOURCES / 'kk3_harness.py')
kh = importlib.util.module_from_spec(spec)
with mock.patch.dict(sys.modules, {'kk3_bridge': bridge}):
    spec.loader.exec_module(kh)


def snapshot():
    names = ['A', 'V', 'period', 'percent', 'Aacute', 'follower', 'opposite']
    codes = [65, 86, 46, 37, 193, None, None]
    infos = {n: types.SimpleNamespace(empty=False, unicode=c, components=['A'] if n == 'Aacute' else [], kern=True)
             for n, c in zip(names, codes)}
    specs = [types.SimpleNamespace(lsb_rule=0, rsb_rule=0, lsb_glyph=bridge.NONE, rsb_glyph=bridge.NONE) for n in names]
    specs[5].lsb_rule = bridge.RULE_FOLLOW_SAME
    specs[5].lsb_glyph = 0
    specs[6].rsb_rule = bridge.RULE_FOLLOW_OPPOSITE
    specs[6].rsb_glyph = 5
    return types.SimpleNamespace(names=names, infos=infos, specs=specs, char_map={}, upm=1000, slant_degrees=0)


def window_methods():
    tree = ast.parse((RESOURCES / 'kk3_window.py').read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'KK3Window')
    names = {'_harness_problem', '_harness_profile', '_harness_identity', 'harness_available', '_harness_strength',
             '_harness_plan', '_harness_busy', 'harnessChanged', 'importHarnessPath', '_solve_key', 'model_pair', '_harness_result_current',
             '_harness_explicit_pairs', 'harness_pair_correction', '_set_result', 'harness_comparison_problem'}
    selected = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Window', bases=[], keywords=[], body=selected, decorator_list=[])], type_ignores=[]))
    env = dict(kh=kh, khp=hp, kb=bridge, os=__import__('os'), math=__import__('math'), traceback=__import__('traceback'))
    exec(compile(module, 'kk3_window.py', 'exec'), env)
    return env['Window']


def inspector_methods():
    tree = ast.parse((RESOURCES / 'kk3_harness_window.py').read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'HarnessWindow')
    names = {'plan', 'refresh', 'result_ready', '_selected_names', 'rowSelected'}
    selected = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Inspector', bases=[], keywords=[], body=selected, decorator_list=[])], type_ignores=[]))
    env = {'COUNT': 80, 'FILTERS': [('text', 'In running text')]}
    exec(compile(module, 'kk3_harness_window.py', 'exec'), env)
    return env['Inspector']


class Control:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


def window():
    w = window_methods()()
    w.w = types.SimpleNamespace(harness=Control(2), harnessStrength=Control(50), tightness=Control(0))
    w.engine = types.SimpleNamespace(features=1)
    w.snapshot = snapshot()
    w.context = None
    w._fontz_harness = profile()
    w._fontz_harness_error = ''
    w._harness_last_mode = w._harness_selection = 2
    w._harness_saved_strength = 50
    w._style = lambda: 'text'
    w._punctuation_on = lambda: True
    w._fitted = 0
    w._glyph_opts = lambda: []
    w._kept_sides = lambda: None
    w._generation = 1
    w.groups = types.SimpleNamespace(key=lambda: ())
    w._harness_cache = None
    w._stepper = w._job = w._job_kind = w.harness_window = None
    w.state = 'ready'
    w._save = mock.Mock()
    w._show_slider_values = w._update_labels = w._request_preview = mock.Mock()
    return w


class RuntimeTest(unittest.TestCase):
    def test_subset_mapping_and_single_table(self):
        data = profile()
        data['categories'] = {'Display': {'left': {'A': [999, 0, 0, 0]}}}
        plan = kh.Plan(snapshot(), 0, 1, profile=data, style='display')
        self.assertEqual(plan.sides[0], [1, 5])
        self.assertEqual(plan.sides[3], [0, 0])
        self.assertIsNone(plan.key[3])
        self.assertEqual(plan.sides[4], [1, 5])
        self.assertEqual(plan.pair_value[(0, 1)], -10)
        self.assertEqual(plan.source_name, 'Fontz')
        self.assertEqual(plan.style, 'text')

    def test_legacy_default_and_diagnostic_callers_keep_google_fonts(self):
        data = profile()
        del data['name']
        del data['provenance']
        data['categories'] = {'Display': {'left': {'A': [7, 0, 0, 0]}}}
        with mock.patch.object(kh, 'table', return_value=data):
            legacy = kh.Plan(snapshot(), 0, 1)
            diagnostic = kh.Plan(snapshot(), 0, 1, style='display', kept=None, punctuation=True)
        self.assertEqual(legacy.sides[0], [1, 5])
        self.assertEqual(diagnostic.sides[0], [8, 5])
        self.assertEqual(legacy.source_name, 'Google Fonts')

    def test_solve_keys_follow_profile_without_moving_diagnostic_tail(self):
        w = window()
        w._physics = lambda: (1, 2, 3)
        w._threshold = lambda: 5
        w._budget = lambda: 0
        w.join_count = 0
        w._join_mode = lambda: 'keep'
        w.category_offsets = {}
        w._keep_fit_on = lambda: False
        w.stay_close = w.caps_to_lower = w.lower_to_caps = 0
        w._exceptions = lambda: 0
        w._small_caps_on = w._figures_on = lambda: True
        before = w._solve_key(False)
        self.assertEqual(before[-5:], (True, True, True, 'text', .5))
        self.assertEqual(w._solve_key(True), before)
        w._fontz_harness['left']['A'][0] += 2
        self.assertNotEqual(before, w._solve_key(False))

    def test_frozen_and_kept_followers_get_zero(self):
        for kwargs in ({'frozen': [0]}, {'kept': ([0], [])}):
            with self.subTest(kwargs=kwargs):
                plan = kh.Plan(snapshot(), 0, 1, profile=profile(), **kwargs)
                self.assertEqual(plan.sides[0][0], 0)
                self.assertEqual(plan.sides[5][0], 0)
                self.assertEqual(plan.sides[6][1], 0)

    def test_plan_cache_and_strength(self):
        w = window()
        plan = w._harness_plan()
        self.assertIs(plan, w._harness_plan())
        self.assertEqual(plan.sides[0], [.5, 2.5])
        w._fontz_harness['left']['A'][0] += 10
        self.assertIsNot(plan, w._harness_plan())
        w.w.harness.set(0)
        self.assertIsNone(w._harness_plan())
        self.assertEqual(w._harness_plan(force_strength=1).source_name, 'Fontz')

    def test_scope_pauses_even_for_forced_preview(self):
        for change, expected in ((lambda w: setattr(w, '_style', lambda: 'display'), 'Text faces'),
                                 (lambda w: setattr(w, '_punctuation_on', lambda: False), 'Punctuation'),
                                 (lambda w: setattr(w.snapshot, 'slant_degrees', 12), 'upright Latin')):
            w = window()
            change(w)
            self.assertIn(expected, w._harness_problem())
            self.assertIsNone(w._harness_plan(force_strength=1))

    def test_mode_change_invalidates_pending_work(self):
        w = window()
        job = mock.Mock()
        w._job, w._job_kind = job, 'preview'
        w._harness_cache, w._result_key = ('old',), ('old',)
        w._apply_when_done = w._apply_after_preview = w._whole_after_preview = True
        w.w.harness.set(1)
        w.harnessChanged(None)
        job.free.assert_called_once()
        self.assertIsNone(w._harness_cache)
        self.assertIsNone(w._result_key)
        self.assertFalse(w._apply_after_preview)
        self.assertEqual(w._harness_last_mode, 1)

    def test_import_selects_new_profile_and_invalidates_cache(self):
        w = window()
        w._harness_cache = ('old',)
        newer = profile()
        newer['left']['A'][0] = 30
        with mock.patch.object(hp, 'import_profile', return_value='/tmp/fontz-harness.json'), mock.patch.object(hp, 'load_fontz_profile', return_value=newer):
            w.importHarnessPath('/tmp/source.json')
        self.assertIs(w._fontz_harness, newer)
        self.assertIsNone(w._harness_cache)
        self.assertEqual(w.w.harness.get(), 2)

    def result_window(self, value, explicit, active):
        w = window()
        data = profile()
        data['pairs'] = {'A V': 3}
        plan = kh.Plan(w.snapshot, 0, 1, profile=data)
        w._result_harness = plan if active else None
        w._result_kind = 'preview'
        w._result_key = ('current',)
        w._solve_key = lambda whole: ('current',)
        w._result_gg = None
        w._threshold = lambda: 5
        w._physics = lambda: (1, 1, 1)
        entries = [(0, 0, 1, value, 1)] if explicit else ([(1, 0, 0, value, 1)] if value else [])
        sides = plan.sides if active else [[0, 0]] * len(w.snapshot.names)
        metrics = [types.SimpleNamespace(lsb=10+s[0], rsb=20+s[1], advance=300+sum(s)) for s in sides]
        w.result = types.SimpleNamespace(ptr=1, metrics=metrics, value=lambda a, b: value,
                                         iter_entries=mock.Mock(return_value=iter(entries)))
        return w, plan

    def test_threshold_edge_new_zero_existing_zero_and_class_pairs(self):
        # Same planned +3: a new zero-base pair is skipped, a zero-valued
        # glyph exception receives it, and class kerning -10 becomes -7.
        cases = [(0, False, 0, False), (0, True, 3, True), (-10, False, -7, True)]
        for base, baseline_explicit, final, final_explicit in cases:
            with self.subTest(base=base, baseline_explicit=baseline_explicit):
                off, plan = self.result_window(base, baseline_explicit, False)
                expected = final-base
                self.assertEqual(off.harness_pair_correction(0, 1, plan), expected)
                on, active_plan = self.result_window(final, final_explicit, True)
                self.assertEqual(on.harness_pair_correction(0, 1, active_plan), expected)
                self.assertEqual(on.model_pair(0, 1), ((10, 20, 300), (10, 20, 300), base))
                self.assertEqual(off.model_pair(0, 1), ((10, 20, 300), (10, 20, 300), base))
                self.assertEqual(on.harness_pair_correction(0, 1, active_plan), expected)
                on.result.iter_entries.assert_called_once()

    def test_off_preview_omits_pair_correction_when_kerning_is_disabled(self):
        w, plan = self.result_window(0, False, False)
        plan.pair_value[(0, 1)] = 10
        w._physics = lambda: (1, 1, 0)
        self.assertEqual(w.harness_pair_correction(0, 1, plan), 0)

    def test_threshold_boundary_and_upm_scale(self):
        w, plan = self.result_window(0, False, False)
        plan.pair_value[(0, 1)] = 5
        self.assertEqual(w.harness_pair_correction(0, 1, plan), 5)
        plan.pair_value[(0, 1)] = -5
        self.assertEqual(w.harness_pair_correction(0, 1, plan), -5)
        w.snapshot.upm = 2000
        self.assertEqual(w.harness_pair_correction(0, 1, plan), 0)
        plan.pair_value[(0, 1)] = -10
        self.assertEqual(w.harness_pair_correction(0, 1, plan), -10)

    def test_stale_or_unrequested_pair_waits(self):
        w, plan = self.result_window(3, True, True)
        w._result_key = ('previous profile',)
        self.assertIsNone(w.model_pair(0, 1))
        self.assertIsNone(w.harness_pair_correction(0, 1, plan))
        w._result_key = ('current',)
        w.result.value = lambda a, b: float('nan')
        self.assertIsNone(w.model_pair(0, 1))
        self.assertIsNone(w.harness_pair_correction(0, 1, plan))

    def test_fixed_advance_and_mixed_frozen_kept_pairs(self):
        snap = snapshot()
        snap.specs[0].flags = bridge.GLYPH_FIXED_ADVANCE
        plan = kh.Plan(snap, 0, 1, profile=profile())
        self.assertEqual(plan.sides[0], [0, 0])
        self.assertEqual(plan.sides[5][0], 0)
        self.assertEqual(plan.sides[6][1], 0)
        for frozen, kept in (([0], ([1], [])), ([1], ([], [0]))):
            plan = kh.Plan(snapshot(), 0, 1, profile=profile(), frozen=frozen, kept=kept)
            self.assertNotIn((0, 1), plan.pair_value)

    def test_follow_groups_disable_only_inspector_comparison(self):
        for flag in (bridge.GLYPHOPT_FOLLOW_SPACING, bridge.GLYPHOPT_FOLLOW_KERNING):
            w, plan = self.result_window(3, True, True)
            w._glyph_opts = lambda: [(False, 0, 1, 0, 0, bridge.NONE, flag)]
            self.assertIn('Follow groups', w.harness_comparison_problem())
            self.assertIsNone(w.model_pair(0, 1))
            self.assertIsNone(w.harness_pair_correction(0, 1, plan))
            self.assertTrue(w.harness_available())
            self.assertIsNotNone(w._harness_plan())
        w._glyph_opts = lambda: [(False, 0, 1, 0, bridge.NONE, bridge.NONE, 3)]
        self.assertEqual(w.harness_comparison_problem(), '')

    def test_inspector_uses_completed_plan_after_fit_updates(self):
        w, applied = self.result_window(3, True, True)
        ui = inspector_methods()()
        ui.main = w
        ui.w = types.SimpleNamespace(strength=Control(100))
        # _set_result can learn a new global/category fit. A reconstructed
        # plan would therefore have different corrections despite identical
        # solve controls; the comparison must use the actual applied plan.
        w._fitted = .5
        w._category_fits = {1: .3, 2: .5}
        reconstructed = w._harness_plan()
        self.assertIsNot(reconstructed, applied)
        self.assertNotEqual(reconstructed.sides, applied.sides)
        w._harness_plan = mock.Mock(return_value=reconstructed)
        self.assertIs(ui.plan(), applied)
        self.assertEqual(w.harness_pair_correction(0, 1, ui.plan()), 3)
        w._harness_plan.assert_not_called()

    def test_result_ready_refreshes_measured_rows_without_preview_churn(self):
        w, plan = self.result_window(0, False, True)
        ui = inspector_methods()()
        ui.main, ui._snap = w, w.snapshot
        ui._closed = False
        ui.pairs, ui.selected = [(0, 1, plan.delta(0, 1))], None
        ui._glyphs = frozenset([0, 1])
        ui.preview = mock.Mock()
        rows = Control([])
        rows.getSelection = lambda: [0]
        rows.setSelection = mock.Mock()
        ui.w = types.SimpleNamespace(strengthField=Control(''), strength=Control(100),
                                     status=Control(''), on=Control(2), which=Control(0), list=rows)
        w._request_preview.reset_mock()
        ui.result_ready()
        # Planned side shifts total 6; planned pair +3 was skipped.
        self.assertEqual(rows.get()[0]['delta'], '+6')
        self.assertEqual(rows.get()[0]['pairc'], '+0')
        self.assertIs(ui.plan(), plan)
        w._request_preview.assert_not_called()
        # Changing source invalidates the result immediately, so no stale
        # measured delta is advertised while the next solve is pending.
        w._result_key = ('old source',)
        ui.result_ready()
        self.assertEqual(rows.get()[0]['delta'], '…')
        w._request_preview.assert_not_called()

    def test_new_result_clears_explicit_pair_cache(self):
        w, plan = self.result_window(3, True, True)
        w._harness_explicit_pairs()
        result = types.SimpleNamespace(fitted_looseness=0, category_fits=lambda: {})
        w._job_harness = plan
        w._retire = w._check_joins = w._panes_due = w._set_status = mock.Mock()
        w._result_status = lambda: ''
        w.joins_window = w.categories_window = None
        w._set_result(result, 'preview', frozenset(), ('new',))
        self.assertIsNone(w._result_gg)

    def test_busy_change_and_import_are_blocked(self):
        w = window()
        w.state = 'applying'
        w.w.harness.set(1)
        w.w.harnessStrength.set(10)
        w.harnessChanged(None)
        self.assertEqual(w.w.harness.get(), 2)
        self.assertEqual(w.w.harnessStrength.get(), 50)
        with self.assertRaises(ValueError):
            w.importHarnessPath('/tmp/source.json')


if __name__ == '__main__':
    unittest.main()
