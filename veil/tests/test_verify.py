import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from veil.stages import verify

REPO = Path(__file__).resolve().parents[2]


def test_claimed_tokens_only_quote_text():
    assert verify.claimed_tokens('Text overlay reading KULKARNI — 12') == ['KULKARNI']
    assert verify.claimed_tokens("sender 'Rohan Kulkarni' with text") == ['ROHAN KULKARNI']
    assert verify.claimed_tokens('delivery box with an address label') == []


def test_found_is_fuzzy_but_not_loose():
    assert verify.found('KULKARNI', ['Kulkarnl - 12'])
    assert not verify.found('KULKARNI', ['def total(items):', 's += i.price'])
