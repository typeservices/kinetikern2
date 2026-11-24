# Fontz Designer Harness for Kinetikern3

The Glyphs plugin offers **Off**, **Google Fonts**, and **Fontz** in its harness selector. Google Fonts retains the upstream table. Fontz is a separate, locally trained profile; selecting it never adds the Google Fonts corrections too. Existing saved On/Off settings are preserved, and new installations remain Off.

Fontz is experimental pending visual review. Its initial scope is upright Latin with **Text faces** conventions and **Punctuation** enabled. Automatic conventions work when they resolve to Text faces. Unsupported conventions, punctuation off, or a slanted master pause Fontz and explain why. Strength remains adjustable. **Harness…** shows the selected profile and offers **Import Fontz…**.

The profile must match both the exact Kinetikern3 engine binary and the punctuation-conventions table. A Kinetikern2 profile cannot be imported. The bundled profile is `plugin/Kinetikern3.glyphsPlugin/Contents/Resources/fontz-harness.json`; a validated local import takes precedence from `~/Library/Application Support/Kinetikern3/Harnesses/`.

## Training and evaluation

The migration preserves the original Fontz inventory and family partitions. There are 542 supported fonts: 294 in 31 training families, 101 in 12 validation families, and 147 in 13 evaluation families. The evaluation families have been examined before; this is not a fresh blind test. Unsupported shaping, incomplete core coverage, italics, variable fonts and fixed-pitch faces have explicit exclusion records. Technically compatible display-labelled fonts remain in the curated corpus; no quality scores are invented.

Each family contributes equal total weight. The six predeclared candidates are constant or looseness/stem-dependent side corrections, each with shrinkage 0.25, 0.5 or 1.0. Pair corrections require cross-family support. Selection uses validation families only; the winner is frozen before final scoring. Numerical gates require at least 5% improvement over the baseline, no worse overall error than Google Fonts, no more than 2% regression in letters or punctuation, no regression in the 90th-percentile family error, and a positive 95% family-bootstrap improvement interval.

Measurements use the unchanged bundled Kinetikern3 engine with the harness off and text punctuation conventions on. Both harnesses are compared on the same original 66-glyph Fontz core, at the same per-font looseness. The comparison also reports Looseness 0. Reference-matched errors subtract the same baseline-derived global offset from every mode; fixed-zero errors do not. Threshold-aware scoring uses actual engine kerning precedence. This is a core-pair evaluation; whole-font rhythm, different user settings, and Cocoa outline/stem extraction still require visual review in Glyphs.

Calibration settings: coupling 1, threshold 5 per 1000 em, unlimited pair budget, classes/window/script scope on, text conventions, no Stay close, category offsets or case-pair offsets. Looseness fitting searches -1 to +1. The original Fontz fonts and Kinetikern2 artifacts are unchanged.

## Reproduction

Use Python 3.11 or 3.12 with `tools/requirements-fontz.txt`. Put the existing frozen manifest in a new run folder; its `root` identifies the local Fontz collection. Never reuse the Kinetikern2 observations. From the Kinetikern3 project:

```sh
python3 tools/kk3_fontz_observe.py --manifest results/fontz-k3/run-2026-11-05/manifest.json --out results/fontz-k3/run-2026-11-05/data --workers 6
python3 tools/kk3_fontz_enrich.py --run results/fontz-k3/run-2026-11-05 --workers 6
python3 tools/kk3_fontz_evaluate.py --data results/fontz-k3/run-2026-11-05/data --out results/fontz-k3/run-2026-11-05 --bundled plugin/Kinetikern3.glyphsPlugin/Contents/Resources/kk3_harness.json
python3 tools/kk3_fontz_report.py --run results/fontz-k3/run-2026-11-05
python3 tools/kk3_fontz_verify.py --run results/fontz-k3/run-2026-11-05
python3 -m unittest discover -s tests -p 'test_fontz_*.py'
```

The observation cache verifies font and protocol identities. Frozen fits reject changed data or fitting code. Relocating the run preserves access through local observation filenames. `report.html` contains private outline proofs, so the run folder is ignored by Git. The runtime uses only the Python standard library and the existing bridge; training dependencies are not needed in Glyphs.

## Glyphs review

The migration edits the local project and produces a separate plugin package; it does not install or restart Glyphs. On a disposable font copy, review Off / Google Fonts / Fontz at several strengths, the Harness pair drawings, whole-font results, Apply and Revert. Check punctuation, accented followers, frozen glyphs, very light/heavy styles, and the proof report's largest regressions. Confirm paused settings and import errors are clear. Static and offline engine checks do not replace this interaction test.

## November 2026 result

The validation-selected candidate has 165 pair corrections. Its side coefficients depend on looseness and stem weight. The held-out comparison is:

| Setting | K3 without harness | Google Fonts | Fontz |
|---|---:|---:|---:|
| Reference-matched looseness | 15.521 | 13.785 | 13.972 |
| Looseness 0 | 30.941 | 30.382 | 30.308 |

Errors are family-balanced mean absolute core-pair gap differences per 1000 em. Fontz improves the matched mean by 9.98%, with a 95% interval of −0.98% to 18.92%. At Looseness 0 the improvement is 2.05%, interval 0.17% to 5.11%.

The candidate fails three numerical gates: it is worse overall than Google Fonts at matched looseness, its 90th-percentile family error regresses, and the matched improvement is statistically inconclusive. It remains **experimental**, with no further tuning after this result.

The private report is `results/fontz-k3/run-2026-11-05/report.html`. The same run folder contains the frozen candidate, complete scores, protocol, exclusions, and engine-parity records.

## Verification completed

All 42 focused tests pass, including profile validation, source selection, cache invalidation, held-out fitting safeguards, threshold-aware inspector corrections, frozen/kept followers and portable result paths. Both profiles were then passed through the production correction Plan and the actual engine at matched and zero looseness for all 542 supported fonts: **2,168 checks passed**, with a maximum difference of 0.00002442 per 1000 em against a tolerance of 0.001. The bundle passes static validation for the configured Glyphs targets; this is not a live Glyphs compatibility claim.

The Harness inspector waits for a matching solve and reports only pair corrections that the engine applies. When user Follow spacing/kerning groups are active, it explicitly withholds the before/after comparison because those groups remap the result after the harness. Normal preview solving and Apply remain available.

No live installation, Apply/Revert interaction, or visual approval was performed. The HTML report's structure and ten inline SVG proofs were checked; browser inspection of the local file was unavailable. Review the report locally before relying on the experimental profile.
