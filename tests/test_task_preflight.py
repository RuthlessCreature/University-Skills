"""Read-only real-file task preparation checks, no HTTP or model service."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from task_preflight import check_task

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'input').mkdir();(self.root/'input/material.json').write_text('{}','utf-8');(self.root/'PROMPT.md').write_text('测试提示词','utf-8')
        self.task={'id':'fixture','skills':['research-intake'],'steps':['intake'],'node_contracts':{'intake':{'goal':'read','output':'intake.json','required_tools':['read_material'],'skill_ids':['research-intake']}}}
    def tearDown(self):self.tmp.cleanup()
    def check(self):
        p=self.root/'task.json';p.write_text(json.dumps(self.task),'utf-8');return check_task(p)
    def test_actual_files_ready_without_semantic_approval(self):
        r=self.check();self.assertEqual(r['status'],'READY_FOR_PROVIDER_PROBE');self.assertFalse(r['network_called']);self.assertFalse(r['semantic_or_scientific_acceptance'])
    def test_missing_file_reported(self):
        self.task['runner_materials']={'missing':'missing.md'}
        self.assertIn('MISSING_FILE',[e['kind'] for e in self.check()['errors']])
    def test_alias_cannot_override_task(self):
        self.task['runner_materials']={'task':'input/material.json'}
        self.assertIn('ALIAS_COLLISION',[e['kind'] for e in self.check()['errors']])
    def test_wrong_node_skill_reported(self):
        self.task['node_contracts']['intake']['skill_ids']=['paper-review']
        self.assertIn('NODE_SKILL_MAPPING',[e['kind'] for e in self.check()['errors']])
    def test_python_source_can_be_read_without_execution(self):
        source=self.root/'source.py';source.write_text('raise RuntimeError("must not execute")','utf-8');self.task['runner_materials']={'source':source.name}
        self.assertFalse(self.check()['errors'])
    def test_missing_export_profile_reported(self):
        self.task['word_export_required']=True
        self.assertIn('MISSING_EXPORT_PROFILE',[e['kind'] for e in self.check()['errors']])

if __name__=='__main__':unittest.main()
