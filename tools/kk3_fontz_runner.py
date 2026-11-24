"""Offline K3 context with the same text punctuation conventions as the plugin."""
from types import SimpleNamespace
import kk3_fonts as kf
import kk3_bridge as kb
import kk3_punctuation as kp

class Runner:
    def __init__(self, cases, threads=1):
        self.engine = kb.Engine(kf.DYLIB)
        if not self.engine.features & kb.FEATURE_PUNCTUATION:
            raise ValueError('K3 engine lacks punctuation conventions')
        self.contexts = {}
        self.punctuation = {}
        self.snapshots = {}
        try:
            for key, case in cases.items():
                packer = kb.InputPacker()
                infos = {}
                specs = []
                for i, name in enumerate(case['names']):
                    ch = case['characters'][i]
                    spec = kb.GlyphSpec(name, case['contours'][i], case['advances'][i],
                                        case['groups'][i], kb.GLYPH_KERN,
                                        kb.script_code('Latn' if ch.isalpha() else 'Zyyy'))
                    specs.append(spec)
                    packer.add(spec)
                    infos[name] = SimpleNamespace(unicode=ord(ch), empty=False, width=case['advances'][i],
                                                   kern=True, components=[])
                snap = SimpleNamespace(names=case['names'], infos=infos, specs=specs, upm=case['upm'],
                                       index={n:i for i,n in enumerate(case['names'])}, generation=0,
                                       char_map=dict(zip(case['characters'], case['names'])))
                self.snapshots[key] = snap
                self.punctuation[key] = kp.engine_arg(snap, 'text')
                self.contexts[key] = kf.run_job(self.engine.prepare(packer, case['upm'], threads))
        except BaseException:
            self.close()
            raise

    def close(self):
        for context in self.contexts.values():
            context.close()
        self.contexts.clear()
        # The runtime cache keys include id(snapshot); release entries before an id can be reused.
        kp._cache.clear()
