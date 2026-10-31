"""Thin HTTP client; processing stays inside the engine."""
from pathlib import Path
import httpx


class VeilClient:
    def __init__(self, base_url='http://127.0.0.1:8000', *, transport=None):
        self.http = httpx.Client(base_url=base_url, timeout=180, transport=transport)

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def create_job(self, path):
        with Path(path).open('rb') as video:
            response = self.http.post('/v1/jobs', files={'video': ('input.mp4', video, 'video/mp4')})
        response.raise_for_status()
        return response.json()

    def process(self, job_id, timeline=None):
        response = self.http.post(f'/v1/jobs/{job_id}/redact', json=timeline)
        response.raise_for_status()
        return response.json()

    def receipt(self, job_id):
        response = self.http.get(f'/v1/jobs/{job_id}/receipt')
        response.raise_for_status()
        return response.json()

    def download(self, job_id, destination):
        target = Path(destination)
        temporary = target.with_name(target.name + '.partial')
        try:
            with self.http.stream('GET', f'/v1/jobs/{job_id}/export') as response:
                response.raise_for_status()
                with temporary.open('wb') as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


    def cloud_action(self, job_id, action, *, seed_omit_phone=False,face_action='cover'):
        if action not in ('detect','verify','repair'):
            raise ValueError('Unsupported cloud action')
        response=self.http.post(f'/v1/jobs/{job_id}/{action}',json={
            'allow_cloud_transfer':True,'media_is_synthetic_or_consented':True,
            'seed_omit_phone':seed_omit_phone,'face_action':face_action})
        response.raise_for_status()
        return response.json()

    def verification(self, job_id):
        response=self.http.get(f'/v1/jobs/{job_id}/verification')
        response.raise_for_status()
        return response.json()


    def protect(self, path, destination, *, allow_cloud_transfer, media_is_synthetic_or_consented, max_repairs=1, face_action='cover'):
        """Real bounded workflow; residuals and utility warnings remain in returned evidence."""
        if allow_cloud_transfer is not True or media_is_synthetic_or_consented is not True:
            raise ValueError('Explicit cloud permission and synthetic/consented-media confirmation required')
        if face_action not in ('cover','blur'):
            raise ValueError('Face action must be cover or blur')
        if max_repairs not in (0,1,2):
            raise ValueError('Repair budget must be 0, 1 or 2')
        job=self.create_job(path)
        self.cloud_action(job['id'],'detect',face_action=face_action)
        self.process(job['id'])
        job=self.cloud_action(job['id'],'verify')
        for _ in range(max_repairs):
            if job['verification']!='residual_observed':break
            self.cloud_action(job['id'],'repair')
            job=self.cloud_action(job['id'],'verify')
        self.download(job['id'],destination)
        return {'job':job,'verification':self.verification(job['id']),'receipt':self.receipt(job['id'])}


    def process_natural(self, job_id, surfaces, *, media_is_synthetic_or_consented, timeline=None):
        """Local natural editing; no cloud transfer by this method. Source controls required."""
        if media_is_synthetic_or_consented is not True:
            raise ValueError('Explicit synthetic/consented-media confirmation required')
        response=self.http.post(f'/v1/jobs/{job_id}/natural',json={
            'media_is_synthetic_or_consented':True,'timeline':timeline,'surfaces':surfaces})
        response.raise_for_status()
        return response.json()

    def natural_review(self, job_id):
        response=self.http.get(f'/v1/jobs/{job_id}/natural-review')
        response.raise_for_status()
        return response.json()

    def protect_natural(self, path, destination, surfaces, *, media_is_synthetic_or_consented, timeline):
        if media_is_synthetic_or_consented is not True:
            raise ValueError('Explicit synthetic/consented-media confirmation required')
        job=self.create_job(path)
        job=self.process_natural(job['id'],surfaces,media_is_synthetic_or_consented=True,timeline=timeline)
        review=self.natural_review(job['id'])
        if job['status']!='rendered':
            return {'job':job,'natural_review':review,'downloaded':False}
        self.download(job['id'],destination)
        return {'job':job,'natural_review':review,'receipt':self.receipt(job['id']),'downloaded':True}
