"""Real filesystem/tool tests. No model service or cloud success is implied."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from local_skill_runner import LocalTools,validate_resume,sha
from provider_adapter import ProviderConfig,ProviderError

class LocalToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.data=self.root/'data.csv';self.data.write_text('species,sex,length\nA,female,10\nA,male,12\nA,male,14\nA,NA,11\nB,male,20\nA,female,NA\n',encoding='utf-8')
        self.tools=LocalTools({'data':self.data},self.root/'output')
    def tearDown(self):self.tmp.cleanup()
    def test_reads_actual_file_and_hash(self):
        result=self.tools.read('data');self.assertIn('A,male,14',result['text']);self.assertEqual(len(result['sha256']),64)
    def test_unregistered_alias_denied(self):
        with self.assertRaises(ValueError):self.tools.read('../data.csv')
    def test_changed_source_denied(self):
        self.data.write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'):self.tools.read('data')
    def test_saved_file_reopens(self):
        r=self.tools.save('draft.md','教学草稿');self.assertEqual(Path(r['path']).read_text('utf-8'),'教学草稿')
    def test_no_overwrite(self):
        self.tools.save('draft.md','first')
        with self.assertRaises(FileExistsError):self.tools.save('draft.md','replacement')
        self.assertEqual((self.root/'output/draft.md').read_text('utf-8'),'first')
    def test_path_escape_denied(self):
        for name in ['../escape.md','..\\escape.md','C:\\escape.md','/escape.md','draft:stream.md']:
            with self.subTest(name=name),self.assertRaises(ValueError):self.tools.save(name,'text')
        self.assertFalse((self.root/'escape.md').exists())
    def test_invalid_json_not_written(self):
        with self.assertRaises(ValueError):self.tools.save('draft.json','{bad}')
        self.assertFalse((self.root/'output/draft.json').exists())
    def test_source_code_is_read_as_text_not_executed(self):
        source=self.root/'source.py';source.write_text('raise RuntimeError("must not execute")','utf-8')
        local=LocalTools({'source':source},self.root/'read-source')
        self.assertIn('must not execute',local.read('source')['text'])
    def test_missing_and_group_statistics(self):
        x=self.tools.summarize('data','species','A','sex','length')
        self.assertEqual(x['all_rows'],6);self.assertEqual(x['filtered_rows'],5)
        self.assertEqual(x['excluded_csv_lines'],[5,7]);self.assertEqual(x['groups']['male']['mean'],13)
        self.assertEqual(x['groups']['male']['source_csv_lines'],[3,4]);self.assertEqual(x['groups']['female']['n'],1)
    def test_unknown_column_denied(self):
        with self.assertRaises(ValueError):self.tools.summarize('data','species','A','sex','invented')
    def test_disabled_provider_not_called(self):
        f=self.root/'config.json';f.write_text(json.dumps({'provider':'minimax','model':'unused','base_url':'https://example.org','key_env':'UNUSED'}),encoding='utf-8')
        with self.assertRaises(ProviderError):ProviderConfig.load(f)
    def test_credentials_in_url_denied(self):
        f=self.root/'config.json';f.write_text(json.dumps({'provider':'openai-compatible','model':'unused','base_url':'https://name:secret@example.org','key_env':'UNUSED'}),encoding='utf-8')
        with self.assertRaises(ProviderError):ProviderConfig.load(f)

class ResumeGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.artifact=self.root/'draft.md';self.artifact.write_text('fixture draft',encoding='utf-8')
        self.node=self.root/'node.json';self.node.write_text(json.dumps({'artifacts':[{'name':'draft.md','sha256':sha(self.artifact)}]}),encoding='utf-8')
        self.inventory={'input':{'sha256':'fixture-input'}}
        self.checkpoint={'input_hashes':self.inventory,'config_sha256':'config-v1','completed_nodes':[{'checkpoint':str(self.node),'sha256':sha(self.node)}]}
    def tearDown(self):self.tmp.cleanup()
    def test_valid_files_can_continue(self):self.assertEqual(len(validate_resume(self.checkpoint,self.inventory,'config-v1',self.root)),1)
    def test_changed_input_rejected(self):
        with self.assertRaises(ProviderError):validate_resume(self.checkpoint,{'input':{'sha256':'changed'}},'config-v1',self.root)
    def test_changed_artifact_rejected(self):
        self.artifact.write_text('changed',encoding='utf-8')
        with self.assertRaises(ProviderError):validate_resume(self.checkpoint,self.inventory,'config-v1',self.root)
    def test_changed_checkpoint_rejected(self):
        self.node.write_text('{}',encoding='utf-8')
        with self.assertRaises(ProviderError):validate_resume(self.checkpoint,self.inventory,'config-v1',self.root)
    def test_changed_provider_rejected(self):
        with self.assertRaises(ProviderError):validate_resume(self.checkpoint,self.inventory,'config-v2',self.root)
    def test_missing_runner_version_rejected(self):
        with self.assertRaisesRegex(ProviderError,'Runner source'):validate_resume(self.checkpoint,self.inventory,'config-v1',self.root,{'runner':'current'})
    def test_changed_runner_rejected(self):
        self.checkpoint['runner_hashes']={'runner':'old'}
        with self.assertRaisesRegex(ProviderError,'Runner source'):validate_resume(self.checkpoint,self.inventory,'config-v1',self.root,{'runner':'new'})
    def test_recorded_runner_version_accepted(self):
        self.checkpoint['runner_hashes']={'runner':'same'}
        self.assertEqual(len(validate_resume(self.checkpoint,self.inventory,'config-v1',self.root,{'runner':'same'})),1)

if __name__=='__main__':unittest.main(verbosity=2)
