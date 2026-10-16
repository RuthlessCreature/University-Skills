import unittest,tempfile,pathlib,sys,json,copy
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from local_workflow import *
class LocalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name)
        self.m=dict(kind='grant',title='测试教学草稿',material_type='teaching-simulation',sources=[dict(id='S',type='teaching-simulation',locator='input section 1')],goals=[dict(id='G',text='复算')],requirements=[dict(id='R',goal_ids=['G'],artifact='code',verification='rerun')],sections=[dict(title='研究目标',content='拟进行对照研究，不声称已有性能结果。',source_ids=['S'])])
        self.write();make_template(self.p/'t.docx',['研究目标'])
    def tearDown(self):self.tmp.cleanup()
    def write(self):
        dump(self.p/'i.json',self.m);dump(self.p/'g.json',dict(type=self.m['material_type'],required_sections=['研究目标'],requirements=self.m['requirements']))
    def execute(self,**kw):return run(self.p/'i.json',self.p/'t.docx',self.p/'out',guide_path=self.p/'g.json',**kw)
    def test_actual_docx_and_no_invented_results(self):
        r=self.execute();self.assertFalse(r['external_model_called']);self.assertFalse(r['human_approved']);d=Document(self.p/'out/grant-draft.docx');txt='\n'.join(x.text for x in d.paragraphs);self.assertIn(self.m['sections'][0]['content'],txt);self.assertNotIn('{{',txt);self.assertIn('HUMAN-SIGNOFF',txt)
    def test_final_export_requires_human(self):
        with self.assertRaisesRegex(WorkflowError,'final_export_blocked'):self.execute(final=True)
        self.assertEqual(load(self.p/'out/run.json')['status'],'failed')
    def test_missing_guide(self):
        with self.assertRaisesRegex(WorkflowError,'guide_required'):run(self.p/'i.json',self.p/'t.docx',self.p/'out')
    def test_changed_guide(self):
        g=load(self.p/'g.json');g['requirements'][0]['artifact']='new';dump(self.p/'g.json',g)
        with self.assertRaisesRegex(WorkflowError,'guide_requirement_mismatch'):self.execute()
    def test_unknown_source(self):
        self.m['sections'][0]['source_ids']=['FAKE'];self.write()
        with self.assertRaisesRegex(WorkflowError,'unknown_source'):self.execute()
    def test_missing_template_section(self):
        make_template(self.p/'t.docx',['错误章节'])
        with self.assertRaisesRegex(WorkflowError,'template_missing_section'):self.execute()
    def test_unmapped_goal(self):
        self.m['goals'].append(dict(id='G2',text='unmapped'));self.write()
        with self.assertRaisesRegex(WorkflowError,'unmapped_goal'):self.execute()
    def test_overlength(self):
        self.m['sections'][0]['max_chars']=2;self.write()
        with self.assertRaisesRegex(WorkflowError,'section_length_exceeded'):self.execute()
    def test_stale_approval(self):
        dump(self.p/'a.json',dict(decision='approved',reviewer_type='human',reviewer='test fixture only',input_sha256='wrong',template_sha256=digest(self.p/'t.docx'),guide_sha256=digest(self.p/'g.json')))
        with self.assertRaisesRegex(WorkflowError,'stale_human_approval'):self.execute(approval_path=self.p/'a.json')
    def test_source_missing_keeps_blocking_issue(self):
        self.m['sections'][0]['source_ids']=[];self.write();self.execute();self.assertTrue(any(x['id'].startswith('SOURCE-') for x in load(self.p/'out/issues.json')))
