import numpy as np
import pytest

from veil.stages import erase_image as ei

W, H = 160, 120


def photo():
    rng = np.random.default_rng(1)
    return (np.linspace(40, 200, H * W * 3).reshape(H, W, 3) + rng.normal(0, 2, (H, W, 3))).clip(0, 255).astype(np.uint8)


BOXES = [ei.Target(box=(10, 10, 60, 40), label='message notification banner'), ei.Target(box=(100, 80, 150, 110), label='text label box')]


def edit_fills_gray(png: bytes, prompt: str) -> np.ndarray:
    return np.full((H * 2, W * 2, 3), 128, np.uint8)  # different size, like the real model


def edit_noop(png: bytes, prompt: str) -> np.ndarray:
    return photo()


def no_ocr(frames, w, h):
    return []


def test_prompt_names_every_target_with_position():
    p = ei.build_prompt(BOXES, (W, H))
    assert 'message notification banner' in p and 'top-left' in p
    assert 'text label box' in p and 'bottom-right' in p
    assert 'unchanged' in p


def test_paste_only_inside_boxes_and_outside_untouched(tmp_path):
    img = photo()
    out, rep = ei.erase(img, BOXES, edit_fills_gray, no_ocr, identifiers=['KULKARNI'], work=tmp_path)
    assert out.shape == img.shape
    far = np.zeros((H, W), bool); far[55:68, 65:85] = True  # well away from both boxes + grow
    assert (out[far] == img[far]).all()
    assert abs(int(out[20:30, 20:50].mean()) - 128) < 5
    assert rep['status'] == 'COVERED'


def test_unchanged_region_is_unresolved(tmp_path):
    _, rep = ei.erase(photo(), BOXES, edit_noop, no_ocr, identifiers=['KULKARNI'], work=tmp_path)
    assert rep['status'] == 'UNRESOLVED'
    assert any('not changed' in r for r in rep['reasons'])


def test_residual_identifier_in_output_is_unresolved(tmp_path):
    def ocr(frames, w, h):
        return [{'time_ms': 0, 'text': 'Rohan Kulkarni'}]
    _, rep = ei.erase(photo(), BOXES, edit_fills_gray, ocr, identifiers=['Kulkarni'], work=tmp_path)
    assert rep['status'] == 'UNRESOLVED' and rep['residual_words']


def test_no_identifiers_means_not_checked(tmp_path):
    _, rep = ei.erase(photo(), BOXES, edit_fills_gray, no_ocr, identifiers=[], work=tmp_path)
    assert rep['status'] == 'NOT_CHECKED'


def test_rejects_empty_or_out_of_frame_boxes(tmp_path):
    with pytest.raises(ValueError):
        ei.erase(photo(), [], edit_fills_gray, no_ocr, identifiers=[], work=tmp_path)
    with pytest.raises(ValueError):
        ei.erase(photo(), [ei.Target(box=(500, 500, 600, 600), label='x')], edit_fills_gray, no_ocr, identifiers=[], work=tmp_path)
