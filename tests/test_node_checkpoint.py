"""Check real local checkpoint evidence; no provider response is simulated."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from local_skill_runner import LocalTools,validate_node_checkpoint,sha
from provider_adapter import ProviderError

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        material=self.root/'material.md';material.write_text('实际材料：不得编造研究基础。','utf-8')
        self.local=LocalTools({n:material for n in ['task','prompt','input/material','skill/grant']},self.root/'out')
        self.events=[]
        for alias in self.local.materials:
            result=self.local.invoke('read_material',{'alias':alias})
            self.events.append({'event':'tool_completed','name':'read_material','arguments':{'alias':alias},'result':result})
        result=self.local.invoke('save_draft',{'name':'section.json','text':json.dumps({'slots':{'background':['材料不足，待补。']}},ensure_ascii=False)})
        self.events.append({'event':'tool_completed','name':'save_draft','arguments':{'name':'section.json'},'result':result})
        self.obj={'status':'DRAFT_READY','artifacts':[{'name':'section.json','sha256':result['sha256']}],'source_locators':[{'alias':'input/material','locator':'paragraph 1','excerpt':'不得编造研究基础'}],'unresolved_questions':[]}
        self.task={'node_contracts':{'background':{'required_tools':['read_material','save_draft'],'required_slots':['background']}}}
    def tearDown(self):self.tmp.cleanup()
    def validate(self,step='background'):
        checkpoint=self.local.output/'checkpoint.json';checkpoint.write_text(json.dumps(self.obj,ensure_ascii=False),'utf-8')
        return validate_node_checkpoint(checkpoint,self.local,self.events,self.task,step)
    def test_actual_fragment_and_source_pass(self):self.assertEqual(self.validate()['status'],'DRAFT_READY')
    def test_claimed_read_without_event_fails(self):
        self.events=self.events[1:]
        with self.assertRaisesRegex(ProviderError,'reads'):self.validate()
    def test_invented_excerpt_fails(self):
        self.obj['source_locators'][0]['excerpt']='已验证实验成功'
        with self.assertRaisesRegex(ProviderError,'excerpt'):self.validate()
    def test_changed_artifact_fails(self):
        (self.local.output/'section.json').write_text('{}','utf-8')
        with self.assertRaisesRegex(ProviderError,'SHA256'):self.validate()
    def test_wrong_slot_fails(self):
        self.task['node_contracts']['background']['required_slots']=['research_content']
        with self.assertRaisesRegex(ProviderError,'slots'):self.validate()
    def test_unrelated_skill_read_rejected(self):
        self.task['node_contracts']['background']['skill_ids']=['grant-background']
        with self.assertRaisesRegex(ProviderError,'assigned'):self.validate()
    def test_export_claim_without_tools_fails(self):
        self.task['word_export_required']=True
        with self.assertRaisesRegex(ProviderError,'export and render'):self.validate('humanize-export')
    def test_blocking_gap_does_not_require_export(self):
        self.task['word_export_required']=True;self.obj.update(status='NEEDS_INPUT',blocking=True,unresolved_questions=['请提供适用模板'])
        self.assertEqual(self.validate('humanize-export')['status'],'NEEDS_INPUT')
    def test_gap_must_name_missing_input(self):
        self.obj['status']='NEEDS_INPUT'
        with self.assertRaisesRegex(ProviderError,'missing'):self.validate()
    def test_figure_claim_without_actual_plot_fails(self):
        self.task['figure_export_required']=True
        with self.assertRaisesRegex(ProviderError,'plot_csv'):self.validate('draw')

if __name__=='__main__':unittest.main()
