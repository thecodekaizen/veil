"""Local jobs with atomic manifests and per-job mutation locks."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4
from veil.core.models import Timeline
from veil.media.inspect import inspect_media, decode_export
from veil.media.redact import render


class Conflict(Exception):
    pass


class JobStore:
    def __init__(self, root: Path, pipeline=None):
        self.pipeline = pipeline
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, job_id):
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            raise FileNotFoundError('Unknown job')
        path = self.root / job_id
        if not path.is_dir():
            raise FileNotFoundError('Unknown job')
        return path

    @staticmethod
    def write(path, value):
        temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        os.replace(temp, path)

    def get(self, job_id):
        return json.loads((self.directory(job_id) / 'job.json').read_text())

    @contextmanager
    def lock(self, job_id):
        path = self.directory(job_id) / '.lock'
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise Conflict('Job is busy; interrupted jobs may require manual lock removal') from exc
        try:
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def create(self, stream):
        job_id = uuid4().hex
        directory = self.root / job_id
        directory.mkdir(mode=0o700)
        source = directory / 'input.mp4'
        try:
            size = 0
            with source.open('wb') as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > 100 * 1024 * 1024:
                        raise ValueError('Upload exceeds 100 MiB')
                    output.write(chunk)
            metadata = inspect_media(source)
            if not metadata['has_audio']:
                raise ValueError('This prototype requires an audio stream')
            job = {'id': job_id, 'status': 'uploaded', 'media': metadata,
                   'detection': 'not_run', 'verification': 'not_run',
                   'needs_human_review': True}
            self.write(directory / 'job.json', job)
            return job
        except Exception:
            shutil.rmtree(directory)
            raise

    def redact(self, job_id, timeline: Timeline | None):
        with self.lock(job_id):
            directory = self.directory(job_id)
            job = self.get(job_id)
            if job['status'] not in ('uploaded', 'detected'):
                raise Conflict('Create a new job to render a different timeline')
            media = job['media']
            automatic = timeline is None
            if timeline is None:
                timeline = Timeline.model_validate_json((directory / 'timeline.json').read_text())
            validate_timeline(timeline,media)
            job['status'] = 'rendering'
            self.write(directory / 'job.json', job)
            try:
                self.write(directory / 'timeline.json', timeline.model_dump(mode='json'))
                render(directory / 'input.mp4', directory / 'export.partial.mp4', timeline)
                inspection = decode_export(directory / 'export.partial.mp4')
                os.replace(directory / 'export.partial.mp4', directory / 'export.mp4')
                receipt = {'job_id': job_id, 'input_sha256': digest(directory / 'input.mp4'),
                           'output_sha256': digest(directory / 'export.mp4'),
                           'timeline_source': 'meta_detection' if automatic else 'client_supplied_reviewed_timeline',
                           'redaction_actions':{track.id:track.action for track in timeline.visual_tracks},
                           'automatic_detection': job['detection'], 'privacy_verification': 'not_run',
                           'needs_human_review': True, 'zero_leaks_guaranteed': False,
                           'media_inspection': inspection, 'render_additional_api_cost_usd': 0}
                calls = json.loads((directory/'calls.json').read_text()) if (directory/'calls.json').exists() else []
                receipt.update(cloud_calls=calls, estimated_api_cost_usd=sum(c.get('estimated_usd',0) for c in calls), billing_reconciled=False)
                self.write(directory / 'receipt.json', receipt)
                job.update(status='rendered', verification='not_run', revision=0)
                self.write(directory / 'job.json', job)
                return job
            except Exception:
                job['status'] = 'failed'
                self.write(directory / 'job.json', job)
                raise
            finally:
                (directory / 'export.partial-silent.mp4').unlink(missing_ok=True)
                (directory / 'export.partial.mp4').unlink(missing_ok=True)


    def natural(self, job_id, request):
        from veil.core.natural import validate_request, execute_natural
        import time
        with self.lock(job_id):
            root=self.directory(job_id);job=self.get(job_id)
            if job['status'] not in ('uploaded','detected'):
                raise Conflict('Natural editing requires a fresh uploaded or detected job')
            timeline=request.timeline
            if timeline is None:
                if not (root/'timeline.json').exists():
                    raise ValueError('Detect first or supply a reviewed protective timeline')
                timeline=Timeline.model_validate_json((root/'timeline.json').read_text())
            validate_timeline(timeline,job['media']);validate_request(request,timeline,job['media'])
            self.write(root/'timeline.json',timeline.model_dump(mode='json'))
            self.write(root/'natural-request.json',request.model_dump(mode='json'))
            job.update(status='natural_rendering',natural_verification='not_run')
            self.write(root/'job.json',job);started=time.monotonic()
            try:
                output,report=execute_natural(root,request,timeline,job['media'])
                report['elapsed_s']=time.monotonic()-started;report['revision']=0
                self.write(root/'natural/report.json',report)
                if output is None:
                    job.update(status='review_required',natural_verification=report['status'],needs_human_review=True)
                    self.write(root/'job.json',job);return job
                shutil.copyfile(output,root/'export.partial.mp4')
                os.replace(root/'export.partial.mp4',root/'export.mp4')
                job.update(status='rendered',revision=0,verification='not_run',
                    natural_verification=report['status'],needs_human_review=True)
                calls=json.loads((root/'calls.json').read_text()) if (root/'calls.json').exists() else []
                receipt={'job_id':job_id,'input_sha256':digest(root/'input.mp4'),'output_sha256':digest(root/'export.mp4'),
                    'revision':0,'privacy_verification':'not_run','natural_editing':report,
                    'timeline_source':'client_supplied_reviewed_timeline' if request.timeline is not None else 'meta_detection',
                    'automatic_detection':job['detection'],'needs_human_review':True,'zero_leaks_guaranteed':False,
                    'media_inspection':report['media_inspection'],'cloud_calls':calls,
                    'estimated_api_cost_usd':sum(c.get('estimated_usd',0) for c in calls),
                    'render_additional_api_cost_usd':0,'billing_reconciled':False}
                self.write(root/'receipt.json',receipt);self.write(root/'job.json',job)
                return job
            except Exception as exc:
                job.update(status='failed',failed_action='natural',error_type=type(exc).__name__)
                self.write(root/'job.json',job);raise
            finally:(root/'export.partial.mp4').unlink(missing_ok=True)

    def natural_review(self,job_id):
        root=self.directory(job_id);path=root/'natural/report.json'
        if not path.exists():return {'status':'not_run'}
        report=json.loads(path.read_text())
        if report.get('export_sha256') and (root/'export.mp4').exists() and report['export_sha256']!=digest(root/'export.mp4'):
            return {'status':'stale','reason':'Current export differs from natural-review hash',
                    'reviewed_export_sha256':report['export_sha256'],'needs_human_review':True}
        return report

    def cloud_action(self, job_id, action, *, seed_omit_phone=False, face_action='cover'):
        if self.pipeline is None:
            raise Conflict('Meta pipeline is not configured')
        with self.lock(job_id):
            root = self.directory(job_id)
            job = self.get(job_id)
            allowed = {'detect': ('uploaded',), 'verify': ('rendered',), 'repair': ('rendered',)}
            if job['status'] not in allowed[action]:
                raise Conflict('Action is unavailable in the current job state')
            if action == 'detect' and job['detection'] != 'not_run':
                raise Conflict('Detection was already attempted; create a new job')
            if action == 'verify' and job['verification'] != 'not_run':
                raise Conflict('Current export already audited; repair before auditing again')
            if action == 'repair' and job['verification'] != 'residual_observed':
                raise Conflict('Repair requires an observed residual exposure')
            previous_status = job['status']
            job['status'] = {'detect': 'detecting', 'verify': 'verifying', 'repair': 'repairing'}[action]
            self.write(root / 'job.json', job)
            try:
                if action == 'detect':
                    self.pipeline.detect(root, job['media'], seed_omit_phone=seed_omit_phone,face_action=face_action)
                    job.update(status='detected', detection='completed', seeded_phone_omission=seed_omit_phone,face_action=face_action)
                elif action == 'verify':
                    report = self.pipeline.verify(root, job['media'], job['revision'])
                    job.update(status='rendered', verification=report['status'],
                               verification_checks_complete=report.get('checks_complete',False))
                    report.update(export_sha256=digest(root/'export.mp4'))
                    self.write(root / 'verification.json', report)
                else:
                    report = json.loads((root/'verification.json').read_text())
                    if report['revision'] != job['revision'] or report['export_sha256'] != digest(root/'export.mp4'):
                        raise ValueError('Audit does not match current export revision')
                    repaired = self.pipeline.repair(root, job['media'], report)
                    # Keep previous output and audit tied to its immutable revision.
                    revision = job['revision']
                    shutil.copyfile(root / 'export.mp4', root / f'export-revision-{revision}.mp4')
                    os.replace(repaired, root / 'export.mp4')
                    job.update(status='rendered', revision=revision+1, verification='not_run',verification_checks_complete=False)
                    if 'natural_verification' in job:job['natural_verification']='invalidated_after_repair'
                self.write(root / 'job.json', job)
                if (root / 'receipt.json').exists():
                    receipt = json.loads((root / 'receipt.json').read_text())
                    receipt.update(output_sha256=digest(root/'export.mp4'), revision=job.get('revision',0),
                                   privacy_verification=job['verification'], needs_human_review=True,
                                   media_inspection=decode_export(root/'export.mp4'))
                    calls = json.loads((root/'calls.json').read_text()) if (root/'calls.json').exists() else []
                    receipt.update(cloud_calls=calls, estimated_api_cost_usd=sum(c.get('estimated_usd',0) for c in calls),
                                   billing_reconciled=False)
                    if action=='verify':
                        receipt['verification_scope']={
                            'revision':job['revision'],'export_sha256':report['export_sha256'],
                            'model_sample_times_ms':report.get('sample_times_ms',[]),
                            'coverage':report.get('coverage'),
                            'check_status':report.get('check_status'),
                            'checks_complete':report.get('checks_complete',False),
                        }
                    elif action=='repair':
                        if 'natural_editing' in receipt:receipt['natural_editing']={'status':'invalidated_after_repair','needs_human_review':True}
                        receipt['verification_scope']={'revision':job['revision'],'status':'not_run'}
                        repair_path=root/'repair-timeline.json'
                        if repair_path.exists():
                            repair_timeline=Timeline.model_validate_json(repair_path.read_text())
                            receipt.setdefault('repair_actions',[]).append({'revision':job['revision'],
                                'tracks':{track.id:track.action for track in repair_timeline.visual_tracks}})
                    self.write(root/'receipt.json',receipt)
                return job
            except Exception as exc:
                job.update(status='failed', failed_action=action, error_type=type(exc).__name__)
                self.write(root/'job.json',job)
                raise


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_timeline(timeline,media):
    if (timeline.width, timeline.height) != (media['width'], media['height']):
        raise ValueError('Timeline dimensions differ from input')
    if abs(timeline.fps - media['fps']) > .001 or abs(timeline.duration_ms - media['duration_ms']) > 100:
        raise ValueError('Timeline timing differs from input')
    for track in timeline.visual_tracks:
        for region in track.regions:
            if region.box[2] > timeline.width or region.box[3] > timeline.height:
                raise ValueError('Region extends beyond input frame')
    if any(i.end_ms > timeline.duration_ms for i in timeline.audio_intervals):
        raise ValueError('Audio interval extends beyond input')
