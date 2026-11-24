import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kk3_fontz_report import summary_html
class ReportTests(unittest.TestCase):
 def test_escapes_font_names_and_shows_failed_gate(self):
  modes={m:{'overall':10,'letters':9,'punctuation':11,'p90':12,'families':{'<script>':{'overall':10}},'fonts':[]} for m in ('Original','Google Fonts','Fontz')}
  modes.update(improvement_percent=0,improvement_ci95=[-1,1])
  e={'test':{'matched':modes,'fixed':modes,'fonts':1,'families':1},'gate':{'pass':False,'reasons':['No improvement']},'exclusions':[{'path':'<bad>','exclusion':'unsupported'}]}
  text=summary_html(e)
  self.assertIn('Experimental',text);self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
  self.assertIn('previously used holdout',text);self.assertNotIn('https://',text)
