"""Proof validation uses actual file tools; no provider is simulated."""
from pathlib import Path
import json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from local_skill_runner import LocalTools,validate_probe_proof
from provider_adapter import ProviderError

class ProbeProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        (root/'input.txt').write_text('actual-file-token','utf-8')
        (root/'data.csv').write_text('kind,group,value\nprobe,check,10\nprobe,check,12\nprobe,check,14\n','utf-8')
        self.local=LocalTools({'probe':root/'input.txt','probe-data':root/'data.csv'},root/'output');self.events=[]
        text=self.invoke('read_material',{'alias':'probe'})['text']
        group=self.invoke('summarize_csv',{'alias':'probe-data','filter_column':'kind','filter_value':'probe','group_column':'group','numeric_column':'value'})['groups']['check']
        self.invoke('save_draft',{'name':'proof.json','text':json.dumps({'read_value':text,'n':group['n'],'mean':group['mean']})})
    def tearDown(self):self.tmp.cleanup()
    def invoke(self,name,args):
        result=self.local.invoke(name,args);self.events.append({'event':'tool_completed','name':name,'arguments':args,'result':result});return result
    def test_actual_tools_and_file_pass(self):self.assertEqual(validate_probe_proof(self.local,'actual-file-token',12,self.events)['mean'],12)
    def test_wrong_nonce_fails(self):
        with self.assertRaises(ProviderError):validate_probe_proof(self.local,'guessed',12,self.events)
    def test_wrong_mean_fails(self):
        with self.assertRaises(ProviderError):validate_probe_proof(self.local,'actual-file-token',13,self.events)
    def test_missing_tool_event_fails(self):
        with self.assertRaises(ProviderError):validate_probe_proof(self.local,'actual-file-token',12,[e for e in self.events if e['name']!='summarize_csv'])

if __name__=='__main__':unittest.main()
