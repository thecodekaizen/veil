import copy
import unittest
from fastapi.testclient import TestClient
from showme.api import app
from showme.session import process_fingerprint, reconcile_session
from test_showme_process import VALID_PROCESS


class SessionTests(unittest.TestCase):
    def check(self, index=1, assessment="consistent", state="separate"):
        return {"id": str(index), "sequence": index, "source": "physical-snapshot",
                "process_sha256": process_fingerprint(VALID_PROCESS), "observation": {
                    "state_id": state, "assessment": assessment, "object_ids": ["red", "blue"],
                    "evidence": "Visible blocks", "uncertainties": [], "view_guidance": "Show joint"}}

    def test_match_offers_next_trace_action(self):
        result = reconcile_session(VALID_PROCESS, [self.check()])
        self.assertEqual(result["next_action"]["transition_id"], VALID_PROCESS["transitions"][0]["id"])
        self.assertEqual(result["current_match"]["state_id"], "separate")

    def test_unclear_preserves_history_not_current_guidance(self):
        result = reconcile_session(VALID_PROCESS, [self.check(), self.check(2, "unclear", "unknown")])
        self.assertEqual(result["last_match"]["sequence"], 1)
        self.assertIsNone(result["current_match"])
        self.assertIsNone(result["next_action"])

    def test_terminal_match_does_not_certify_completion_or_recovery(self):
        result = reconcile_session(VALID_PROCESS, [self.check(1, "possible_divergence", "unknown"), self.check(2, state="stacked")])
        self.assertEqual(result["recovery_status"], "unverified")
        self.assertEqual(result["completion_status"], "not_assessed")

    def test_rejects_simulated_progress(self):
        check = self.check(); check["source"] = "simulation"
        with self.assertRaisesRegex(ValueError, "simulation"):
            reconcile_session(VALID_PROCESS, [check])

    def test_rejects_other_process_revision(self):
        check = self.check(); check["process_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "revision"):
            reconcile_session(VALID_PROCESS, [check])

    def test_rejects_duplicate_and_out_of_order(self):
        for checks in ([self.check(), self.check()], [self.check(2), self.check(1)]):
            with self.assertRaises(ValueError):
                reconcile_session(VALID_PROCESS, checks)

    def test_replay_is_deterministic_and_nonmutating(self):
        checks = [self.check()]; original = copy.deepcopy(checks)
        self.assertEqual(reconcile_session(VALID_PROCESS, checks), reconcile_session(VALID_PROCESS, checks))
        self.assertEqual(checks, original)

    def test_branch_withholds_single_action(self):
        process = copy.deepcopy(VALID_PROCESS)
        alternative = copy.deepcopy(process["transitions"][0]); alternative["id"] = "alternate"
        process["transitions"].append(alternative)
        check = self.check(); check["process_sha256"] = process_fingerprint(process)
        result = reconcile_session(process, [check])
        self.assertTrue(result["branch_requires_review"])
        self.assertIsNone(result["next_action"])

    def test_empty_history_has_no_current_match(self):
        self.assertIsNone(reconcile_session(VALID_PROCESS, [])["current_match"])

    def test_http_round_trip_and_invalid_source(self):
        client = TestClient(app)
        response = client.post("/api/skills/reconcile-session", json={"process": VALID_PROCESS, "checks": [self.check()]})
        self.assertEqual(response.status_code, 200, response.text)
        check = self.check(); check["source"] = "simulation"
        self.assertEqual(client.post("/api/skills/reconcile-session", json={"process": VALID_PROCESS, "checks": [check]}).status_code, 422)
