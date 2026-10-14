import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/"tools/evidence_gate.py"
spec=importlib.util.spec_from_file_location("evidence_gate",path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestEvidenceGate(unittest.TestCase):
    def test_complete_verified(self):
        item={"claims":[{"id":"c1","statement":"模拟A组均值高于B组","status":"VERIFIED",
                         "source":{"document_id":"mock.csv","locator":"row 1-5","evidence_excerpt":"A:5,B:4"}}]}
        self.assertEqual(mod.check_ledger(item)["decision"],"STRUCTURE_PASS")
    def test_missing_locator(self):
        item={"claims":[{"id":"c1","statement":"claim","status":"VERIFIED","source":{"document_id":"a.pdf"}}]}
        self.assertEqual(mod.check_ledger(item)["decision"],"BLOCKED")
    def test_pending(self):
        item={"claims":[{"id":"c1","statement":"claim","status":"PENDING"}]}
        self.assertEqual(mod.check_ledger(item)["decision"],"REVIEW")
    def test_unsupported(self):
        item={"claims":[{"id":"c1","statement":"claim","status":"UNSUPPORTED"}]}
        self.assertEqual(mod.check_ledger(item)["decision"],"BLOCKED")
    def test_duplicate(self):
        item={"claims":[{"id":"x","statement":"a","status":"PENDING"},{"id":"x","statement":"b","status":"PENDING"}]}
        self.assertEqual(mod.check_ledger(item)["decision"],"BLOCKED")
