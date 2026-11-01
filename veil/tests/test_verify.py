import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from veil.stages import verify

REPO = Path(__file__).resolve().parents[2]


def test_claimed_tokens_only_quote_text():
    assert verify.claimed_tokens('Text overlay reading KULKARNI — 12') == ['KULKARNI']
    assert 'ROHAN KULKARNI' in verify.claimed_tokens("sender 'Rohan Kulkarni' with text")
    assert verify.claimed_tokens('delivery box with an address label') == []


def test_found_is_fuzzy_but_not_loose():
    assert verify.found('KULKARNI', ['Kulkarnl - 12'])
    assert not verify.found('KULKARNI', ['def total(items):', 's += i.price'])


def test_load_calls_includes_set_aside_ledgers(tmp_path):
    from veil.report import ledger_summary, load_calls
    (tmp_path / 'calls.json').write_text(json.dumps([{'status': 'completed', 'estimated_usd': 0.01}]))
    (tmp_path / 'calls.gate-run.json').write_text(json.dumps([{'status': 'completed', 'estimated_usd': 0.2},
                                                              {'status': 'failed', 'estimated_usd': None}]))
    calls = load_calls(tmp_path)
    assert len(calls) == 3
    assert ledger_summary(calls) == '3 model calls, 1 failed, est. $0.21 (1 calls without a price estimate)'


def test_proper_names_are_claims_and_match_by_word():
    toks = verify.claimed_tokens('Message notification showing sender name Rohan Kulkarni')
    assert 'ROHAN KULKARNI' in toks
    assert verify.found('ROHAN KULKARNI', ['KULKARNI - 12'])           # the door plate still verifies
    assert verify.found('ROHAN KULKARNI', ['Messages • now', 'Rohan Kulkarni'])
    assert not verify.found('ROHAN KULKARNI', ['def total(items):', 'for i in items:'])  # the code panel is rejected
    assert verify.claimed_tokens('Message notification banner at top') == []  # sentence-initial words are not names
