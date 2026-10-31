# Natural editing API and SDK (bounded local pilot)

The original detection/redaction/verification routes remain compatible. Natural editing is opt-in and local; it reuses reviewed or saved Meta protective tracks. It does not promise general privacy or publishable appearance.

## HTTP

`POST /v1/jobs/{id}/natural` accepts a fresh uploaded/detected job:

```json
{
  "media_is_synthetic_or_consented": true,
  "timeline": null,
  "surfaces": [{
    "track_id": "plate-7",
    "start_frame": 0,
    "kind": "plate",
    "original_identifiers": ["TEST0146"]
  }]
}
```

- `timeline: null` uses the job's existing detection timeline. A supplied reviewed Timeline is also accepted and explicitly labeled client-supplied.
- Optional `corners` is one initial `[TL,TR,BR,BL]` quadrilateral in source pixels. If absent, local contours propose corners inside the protective region. SAM boxes do not automatically establish plane corners.
- `kind` is `plate`, `screen` or `document`; these select fixed local DEMO/PRIVATE templates. Screen/document rendering is implemented for supplied regions, but those categories lack footage validation. No general screen/document detector is claimed.
- No asset paths, uploaded textures, expected labels or per-frame replacement quads are accepted through HTTP.
- At most 8 seeds, 16 original values per seed, 512 decoded frames, and 256 million decoded pixels per all-frame audit. No silent sampling to fit budget.
- Original values are local private job policy inputs. Do not commit real identifiers. Before targeted clearance, full source values must be independently observed at least once by local OCR.

Processing: source positive control → one asset per object → LK/RANSAC tracking → existing renderer → actual exported-file OCR → at most one affected-track opaque fallback → fresh output OCR → separate utility diagnostics. Missing/failed audit or unobserved source values leave `status: review_required` and block `/export`.

Success of these checks yields `status: rendered`, `natural_verification: original_identifier_check_completed_visual_review_required`. It is NOT a general privacy pass, visual-quality pass, anonymity certificate or six-case success. The ordinary `verification` remains `not_run` until the existing broad verifier is explicitly requested.

`GET /v1/jobs/{id}/natural-review` returns source/candidate/final audit status, exact export hash/revision, per-track final strategies, fallback frames/reasons, asset hashes, tracking diagnostics and separate visual review. It returns `stale` after export bytes change. Existing repair invalidates the natural review and receipt scope. `GET /receipt` includes the scoped evidence; `GET /export` downloads only a promoted output.

## SDK

```python
from veil import VeilClient

# reviewed_timeline is an actual reviewed/detected timeline, not fixture geometry
# silently applied to an unrelated input.
with VeilClient("http://127.0.0.1:8020") as client:
    result = client.protect_natural(
        "synthetic-input.mp4", "candidate-for-review.mp4",
        [{"track_id": "plate-7", "start_frame": 0,
          "kind": "plate", "original_identifiers": ["TEST0146"]}],
        media_is_synthetic_or_consented=True,
        timeline=reviewed_timeline,
    )
    print(result["downloaded"], result["natural_review"]["status"])
```

For a Meta-detected job: create/upload, explicitly authorize `/detect` using existing API, then call `process_natural(job_id, surfaces, media_is_synthetic_or_consented=True)` without a timeline. Detection uses cloud inference; natural rendering/local OCR adds no cloud calls. General `/verify` still uses actual exported-frame Spark, Voice and independent OCR; its scope is sampled and separately recorded. The native OCR dependency is macOS Vision; unavailable systems withhold targeted clearance.

## Reproduction and evidence

`natural_api_roundtrip.py` exercises actual SDK/HTTP, local contour initialization, wrong initialization and occlusion on existing synthetic footage. Modes are diagnostic variants, not independent dataset cases. `natural_saved_detection_roundtrip.py` reuses saved real SAM/Spark/Voice geometry without fresh inference. `audit_natural_with_meta.py` intentionally requests one two-call broad Meta output audit; it must not run casually as a unit test.

See NATURAL_INTEGRATION_RESULTS.md. Optional room-tone audio editing and generative removal are not implemented; original audio mute behavior remains.
