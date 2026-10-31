"""Local native-OCR integration tests. No model responses or cloud calls."""
import json
from pathlib import Path
import platform
import shutil
import pytest
from fastapi.testclient import TestClient
from veil.api.app import create_app
from veil.core.natural import NaturalRequest, SurfaceSeed, contour_corners
from veil.media.inspect import decode_export

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'artifacts/natural-surface-001'


def payload(corners=True):
    timeline=json.loads((FIXTURE/'timeline.json').read_text())
    seed={'track_id':'plate-001','start_frame':0,'kind':'plate','original_identifiers':['2025550146']}
    if corners:seed['corners']=json.loads((FIXTURE/'surface-plan.json').read_text())['frames'][0]['corners']
    return {'media_is_synthetic_or_consented':True,'timeline':timeline,'surfaces':[seed]}


def upload(client):
    with (FIXTURE/'original.mp4').open('rb') as source:
        response=client.post('/v1/jobs',files={'video':('input.mp4',source,'video/mp4')})
    assert response.status_code==201,response.text
    return response.json()['id']


@pytest.fixture
def native(monkeypatch):
    if platform.system()!='Darwin' or not shutil.which('swiftc'):pytest.skip('Native macOS OCR unavailable')
    monkeypatch.setenv('VEIL_OCR_CACHE',str(ROOT/'artifacts/private/ocr-cache'))


def test_natural_schema_rejects_asset_paths_and_missing_consent():
    request=payload();request['surfaces'][0]['asset_path']='/etc/passwd'
    with pytest.raises(ValueError):NaturalRequest.model_validate(request)
    request=payload();request['media_is_synthetic_or_consented']=False
    with pytest.raises(ValueError):NaturalRequest.model_validate(request)
    request=payload();request['surfaces'][0]['corners']=[[0,0]]
    with pytest.raises(ValueError):NaturalRequest.model_validate(request)


def test_invalid_track_does_not_start_processing(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client);request=payload();request['surfaces'][0]['track_id']='missing'
        response=client.post(f'/v1/jobs/{ident}/natural',json=request)
        assert response.status_code==422
        assert client.get(f'/v1/jobs/{ident}').json()['status']=='uploaded'
        assert not (tmp_path/ident/'natural').exists()


def test_missing_ocr_blocks_export_unit_state_only(tmp_path,monkeypatch):
    # Inject adapter unavailability only; not model/vision success evidence.
    import veil.core.natural as natural
    monkeypatch.setattr(natural,'audit_export_text',lambda *args,**kwargs:{
        'status':'review_incomplete','residual_findings':[],'needs_manual_review':True})
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client)
        response=client.post(f'/v1/jobs/{ident}/natural',json=payload())
        assert response.status_code==200,response.text
        assert response.json()['status']=='review_required'
        assert client.get(f'/v1/jobs/{ident}/export').status_code==409
        assert client.get(f'/v1/jobs/{ident}/natural-review').json()['status']=='review_required'


def test_real_local_api_replacement_and_revision_hash(tmp_path,native):
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client)
        response=client.post(f'/v1/jobs/{ident}/natural',json=payload())
        assert response.status_code==200,response.text
        job=response.json();assert job['status']=='rendered' and job['verification']=='not_run'
        review=client.get(f'/v1/jobs/{ident}/natural-review').json()
        assert review['final_audit']['status']=='no_original_identifier_observed_in_checked_frames'
        assert review['final_audit']['frame_count']==72
        assert review['visual_quality']['status']=='review_required'
        assert review['rejected_track_ids']==[]
        assert review['render']['natural_replacement']['natural_frames']==72
        receipt=client.get(f'/v1/jobs/{ident}/receipt').json()
        assert receipt['output_sha256']==review['final_audit']['export_sha256']
        assert receipt['privacy_verification']=='not_run' and receipt['zero_leaks_guaranteed'] is False
        assert client.get(f'/v1/jobs/{ident}/export').status_code==200
        assert client.post(f'/v1/jobs/{ident}/natural',json=payload()).status_code==409
        # A different current byte sequence must invalidate the saved natural review.
        path=tmp_path/ident/'export.mp4';path.write_bytes(path.read_bytes()+b'changed')
        assert client.get(f'/v1/jobs/{ident}/natural-review').json()['status']=='stale'
        assert client.get(f'/v1/jobs/{ident}/export').status_code==409


def test_real_wrong_geometry_is_rejected_and_covered(tmp_path,native):
    request=payload()
    request['surfaces'][0]['corners']=[[x+110,y] for x,y in request['surfaces'][0]['corners']]
    for r in request['timeline']['visual_tracks'][0]['regions']:r['box'][2]+=115
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client);response=client.post(f'/v1/jobs/{ident}/natural',json=request)
        assert response.status_code==200,response.text
        assert response.json()['status']=='rendered'
        review=client.get(f'/v1/jobs/{ident}/natural-review').json()
        assert review['rejected_track_ids']==['plate-001']
        assert review['candidate_audit']['status']=='residual_observed'
        assert review['final_audit']['status']=='no_original_identifier_observed_in_checked_frames'
        assert review['applied_strategies']['plate-001']=='opaque_redaction'
        assert (tmp_path/ident/'natural/candidate.mp4').exists()
        assert (tmp_path/ident/'natural/fallback.mp4').exists()


def test_contour_candidate_is_geometric_not_ground_truth():
    import cv2,numpy as np
    image=np.full((120,240,3),70,np.uint8);cv2.rectangle(image,(30,35),(210,90),(230,230,230),-1)
    corners=contour_corners(image,[15,20,225,105])
    assert corners is not None
    assert np.max(np.linalg.norm(np.asarray(corners)-np.asarray([[30,35],[210,35],[210,90],[30,90]]),axis=1))<4


def test_sdk_natural_confirmation_before_network():
    from veil import VeilClient
    with VeilClient() as client:
        with pytest.raises(ValueError):client.protect_natural('absent','absent',[],media_is_synthetic_or_consented=False,timeline={})



def test_source_values_not_observed_withhold_export(tmp_path,native):
    request=payload();request['surfaces'][0]['original_identifiers']=['1234567890']
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client);response=client.post(f'/v1/jobs/{ident}/natural',json=request)
        assert response.status_code==200,response.text
        assert response.json()['status']=='review_required'
        assert client.get(f'/v1/jobs/{ident}/export').status_code==409
        report=client.get(f'/v1/jobs/{ident}/natural-review').json()
        assert report['source_check']['full_identifier_recovered_frames']==0
        assert not (tmp_path/ident/'natural/candidate.mp4').exists()


def test_all_frame_audit_rejects_silent_subsampling(tmp_path):
    from veil.verification.original_text import audit_export_text
    with pytest.raises(ValueError,match='budget'):
        audit_export_text(FIXTURE/'original.mp4',['2025550146'],tmp_path/'audit',tmp_path/'cache',max_frames=2)


def test_natural_rejects_excessive_frame_budget_before_processing(tmp_path):
    from veil.core.natural import validate_request
    from veil.core.models import Timeline
    request=NaturalRequest.model_validate(payload());t=request.timeline
    with pytest.raises(ValueError,match='512'):
        validate_request(request,t,{'duration_ms':60000,'fps':60,'width':640,'height':360})


def test_natural_review_invalidated_by_existing_repair_path(tmp_path,native):
    # The state transition is stubbed only; native rendering/OCR remains real.
    class RevisionOnlyPipeline:
        def verify(self,root,media,revision):
            return {'revision':revision,'status':'residual_observed','frames':[],'spoken_phone_intervals':[]}
        def repair(self,root,media,report):
            # Append a non-image byte: test hash/revision invalidation, not privacy repair.
            path=root/'repair.partial.mp4';path.write_bytes((root/'export.mp4').read_bytes()+b'revision')
            return path
    app=create_app(tmp_path,pipeline=RevisionOnlyPipeline())
    with TestClient(app) as client:
        ident=upload(client)
        assert client.post(f'/v1/jobs/{ident}/natural',json=payload()).json()['status']=='rendered'
        app.state.store.cloud_action(ident,'verify');app.state.store.cloud_action(ident,'repair')
        assert client.get(f'/v1/jobs/{ident}/natural-review').json()['status']=='stale'
        assert client.get(f'/v1/jobs/{ident}/export').status_code==409
        assert client.get(f'/v1/jobs/{ident}/receipt').json()['natural_editing']['status']=='invalidated_after_repair'



def test_short_visible_numeric_fragments_require_review_unit():
    from veil.verification.original_text import short_numeric_warnings
    rows=[{'time_ms':0,'text':'20'},{'time_ms':100,'text':'DEMO'},{'time_ms':200,'text':'999'}]
    warnings=short_numeric_warnings(rows,['2025550146'])
    assert len(warnings)==1 and warnings[0]['possible_numeric_fragment']=='20'


def test_short_fragment_never_promotes_export_unit_state_only(tmp_path,monkeypatch):
    import veil.core.natural as natural
    def controlled_audit(export,identifiers,root,cache):
        if 'source-check' in str(root):return {'status':'residual_observed','residual_findings':[{'original_identifier_index':0,'full_identifier':True}]}
        return {'status':'possible_short_fragment_requires_review','residual_findings':[]}
    monkeypatch.setattr(natural,'audit_export_text',controlled_audit)
    with TestClient(create_app(tmp_path)) as client:
        ident=upload(client);response=client.post(f'/v1/jobs/{ident}/natural',json=payload())
        assert response.status_code==200 and response.json()['status']=='review_required'
        assert client.get(f'/v1/jobs/{ident}/export').status_code==409
