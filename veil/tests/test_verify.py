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


def test_natural_text_mapping_and_rewrite_are_fictional():
    from veil.stages.natural_text import build_mapping, rewrite
    m = build_mapping(['KULKARNI', 'Rohan', 'Kulkarni'], ['KULKARNI', 'ROHAN KULKARNI'])
    assert m == {'KULKARNI': 'SHARMA', 'ROHAN': 'Aarav'}
    assert rewrite('KULKARNI - 12', m) == 'SHARMA - 87'
    assert rewrite('Rohan Kulkarni', m) == 'Aarav Sharma'
    assert rewrite('Your parcel is at the gate', m) == 'Your parcel is at the gate'


def test_natural_text_given_name_from_rows_and_no_false_given():
    from veil.stages.natural_text import build_mapping
    assert build_mapping(['KULKARNI'], ['KULKARNI', 'KULKARNI — 12']) == {'KULKARNI': 'SHARMA'}
    assert build_mapping(['KULKARNI', 'Rohan', 'Kulkarni'], ['KULKARNI', 'Rohan Kulkarni']) == {'KULKARNI': 'SHARMA', 'ROHAN': 'Aarav'}


def test_natural_text_overrides_replace_auto_pool():
    from veil.stages.natural_text import build_mapping, rewrite
    m = build_mapping(['KULKARNI', 'Rohan', 'Kulkarni'], ['KULKARNI', 'Rohan Kulkarni'], overrides={'rohan': 'Priya', 'KULKARNI': 'Verma'})
    assert rewrite('Rohan Kulkarni', m) == 'Priya Verma'
    assert rewrite('KULKARNI - 12', m) == 'VERMA - 87'
    # words without an override keep the deterministic pool
    m2 = build_mapping(['KULKARNI', 'Rohan', 'Kulkarni'], ['KULKARNI', 'Rohan Kulkarni'], overrides={'rohan': 'Priya'})
    assert rewrite('Rohan Kulkarni', m2) == 'Priya Sharma'


def test_parse_overrides_cli_syntax():
    from veil.stages.natural_text import parse_overrides
    assert parse_overrides(['Rohan=Priya', ' kulkarni = Verma ']) == {'ROHAN': 'Priya', 'KULKARNI': 'Verma'}
    import pytest
    with pytest.raises(ValueError):
        parse_overrides(['nonsense'])



def test_natural_identifiers_skip_quoted_sentences_and_generic_words():
    # real claims from a c2 run: Spark quoted the whole notification and used descriptive caps words
    from veil.stages.natural_text import identifying_words
    claims = ['KULKARNI', 'MESSAGE', 'ROHAN KULKARNI', 'YOUR PARCEL IS AT THE GATE', 'GOLD', 'KULKARNI — 12', 'TEXT', 'NAME', 'PHONE']
    assert {w.upper() for w in identifying_words(claims)} == {'KULKARNI', 'ROHAN'}
