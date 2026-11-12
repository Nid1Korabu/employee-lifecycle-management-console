import tempfile, unittest
from pathlib import Path
from src.generator import generate
from src.database import get_connection
from src.validation import detect_findings, run_checks

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"demo.db"; self.exports=Path(self.tmp.name)/"exports"
        generate(50,self.db,20261112,self.exports,True)
    def tearDown(self): self.tmp.cleanup()
    def test_master_and_volume_counts(self):
        with get_connection(self.db) as c:
            self.assertEqual(c.execute("select count(*) from employees").fetchone()[0],50)
            self.assertEqual(c.execute("select count(*) from tasks where onboarding_case_id is not null").fetchone()[0],400)
            self.assertEqual(c.execute("select count(*) from assets").fetchone()[0],1200)
    def test_five_anomaly_types_detected(self):
        types={x["issue_type"] for x in detect_findings(self.db)}
        self.assertTrue({"ACCESS_BEFORE_START_OR_APPROVAL","DUPLICATE_ASSET_ASSIGNMENT","TERMINATED_EMPLOYEE_ACTIVE_GRANT","TASK_DEPENDENCY_CYCLE","RECOVERED_ASSET_STILL_ASSIGNED"}.issubset(types))
    def test_foreign_keys_valid(self):
        with get_connection(self.db) as c: self.assertEqual(len(c.execute("pragma foreign_key_check").fetchall()),0)
    def test_ground_truth_separate(self):
        self.assertTrue((self.exports/"ground_truth.csv").exists())
        with get_connection(self.db) as c:
            names=[r[0] for r in c.execute("select name from sqlite_master where type='table'")]
            self.assertNotIn("ground_truth",names)
    def test_structural_checks(self):
        self.assertTrue(all(ok for _,ok,_ in run_checks(self.db)))

if __name__=="__main__": unittest.main()
