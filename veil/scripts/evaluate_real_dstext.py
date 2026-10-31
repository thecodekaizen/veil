"""Real recorded DSText diagnostic. No generated input or cloud transfers.

Text is a selected product label, not personal data. Dataset labels are used
only after tracking to measure geometric error. Source OCR supplies protection.
Silent media support is tested against the unmodified engine and API.
"""
import json,time,hashlib,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
import cv2,numpy as np,httpx
from veil.core.models import Timeline,VisualTrack,FrameRegion
from veil.media.surface import SurfaceRenderer,SurfaceReplacement
from veil.media.surface_tracking import track_surface
from veil.core.natural import make_asset,quality_review
from veil.verification.ocr import inspect_text
from veil.media.redact import apply_redactions,render
from veil.providers.common import save

root=Path('artifacts/private/real-dataset-001');out=root/'results';out.mkdir(exist_ok=False)
cache=Path('artifacts/private/ocr-cache');started=time.monotonic()
source=root/'source/Activity/Video_170_7_0.mp4'
clip=out/'real-store.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-vf','scale=960:540','-c:v','libx264','-crf','18','-an',str(clip)],check=True)
c=cv2.VideoCapture(str(clip));frames=[];paths=[];i=0
while True:
 ok,f=c.read()
 if not ok:break
 frames.append(f);p=out/f'source-{i:04}.jpg';cv2.imwrite(str(p),f);paths.append((round(i/15*1000),p));i+=1
c.release()
ocr=inspect_text(paths,960,540,cache,include_text_rows=True);save(out/'source-ocr.json',ocr)
# Source OCR selects one label by nearest previous center, not dataset answers.
regions=[];center=np.array([390.,183.]);boxes={};matches=[]
for i in range(len(frames)):
 rows=[r for r in ocr.get('text_rows',[]) if r['time_ms']==round(i/15*1000) and 'QUAKER' in r['text'].upper()]
 candidates=[]
 for r in rows:
  b=np.array(r['box'])*[960,540,960,540];mid=(b[:2]+b[2:])/2
  candidates.append((float(np.linalg.norm(mid-center)),b,mid,r))
 if candidates:
  d,b,mid,r=min(candidates,key=lambda x:x[0])
  if d<100:
   center=mid;box=(max(0,b[0]-5),max(0,b[1]-5),min(960,b[2]+5),min(540,b[3]+5));boxes[i]=box
   regions.append(FrameRegion(frame=i,box=box));matches.append({'frame':i,'text':r['text'],'box':list(box)})
save(out/'associated-ocr.json',matches)
seed=[[337,168],[438,168],[438,198],[337,198]] # one manually selected source-frame word region
geometry,tracking=track_surface(clip,seed);save(out/'tracking.json',tracking)
track=VisualTrack(id='selected-label',category='phone_number',source='local OCR selected public brand; category adapter only, NOT phone detection',regions=regions)
tl=Timeline(duration_ms=round(len(frames)/15*1000),fps=15,width=960,height=540,visual_tracks=[track],audio_intervals=[])
save(out/'timeline.json',tl.model_dump(mode='json'))
asset=out/'asset.png';make_asset(asset,'document',seed)
plan=SurfaceReplacement(track_id=track.id,asset_path=str(asset),geometry_source='one manual source word region; LK; no dataset label input',frames=[g for g in geometry if g.frame in boxes])
engine_error=None
try:render(clip,out/'engine-render.mp4',tl,natural_replacements=[plan])
except Exception as exc:engine_error={'type':type(exc).__name__,'message':str(exc),'reason':'Actual input has no audio; renderer requires audio mapping'}
# Diagnostic compositing uses the exact core SurfaceRenderer and redaction functions,
# then a video-only encode. This does not turn unsupported API input into success.
surface=SurfaceRenderer([plan],tl)
for name in ['opaque','natural']:
 silent=out/(name+'-intermediate.mp4');w=cv2.VideoWriter(str(silent),cv2.VideoWriter_fourcc(*'mp4v'),15,(960,540))
 for i,frame in enumerate(frames):
  f=frame.copy();done=surface.apply(f,i) if name=='natural' else set()
  if i in boxes and track.id not in done:apply_redactions(f,[(boxes[i],'cover')])
  w.write(f)
 w.release();subprocess.run(['ffmpeg','-v','error','-y','-i',str(silent),'-c:v','libx264','-crf','18',str(out/(name+'.mp4'))],check=True)
save(out/'render-decisions.json',surface.report())
# Independent output OCR uses fixed original source target crops. No renderer geometry.
reviews={}
for name in ['original','opaque','natural']:
 cp=cv2.VideoCapture(str(clip if name=='original' else out/(name+'.mp4')));crops=[];index=0
 while True:
  ok,f=cp.read()
  if not ok:break
  if index in boxes:
   x1,y1,x2,y2=map(int,boxes[index]);p=out/f'{name}-crop-{index:04}.png';cv2.imwrite(str(p),f[y1:y2,x1:x2]);crops.append((round(index/15*1000),p))
  index+=1
 cp.release();r=inspect_text(crops,960,540,cache,include_text_rows=True);save(out/(name+'-target-ocr.json'),r)
 hits=[r for r in r.get('text_rows',[]) if any(f in r['text'].upper() for f in ['QUAK','UAKE','AKER'])]
 reviews[name]={'original_word_or_four_letter_fragment_frames':len(set(r['time_ms'] for r in hits)),'target_crop_frames':len(crops)}
# Independent dataset corner benchmark. Dataset ID37 never enters tracker or compositor.
truth=ET.parse(root/'annotations/Activity/Video_170_7_0_GT.xml').getroot();ious=[]
for i,frame in enumerate(truth):
 obj=next((o for o in frame if o.get('ID')=='37'),None)
 if obj is None or i>=len(geometry) or geometry[i].corners is None:continue
 a=np.array(geometry[i].corners,np.float32);b=np.array([[float(p.get('x'))/2,float(p.get('y'))/2] for p in obj],np.float32)
 inter=cv2.intersectConvexConvex(a,b)[0];union=cv2.contourArea(a)+cv2.contourArea(b)-inter
 ious.append(float(inter/union) if union else 0)
api={}
try:
 with source.open('rb') as f:
  r=httpx.post('http://127.0.0.1:8020/v1/jobs',files={'video':('real-store.mp4',f,'video/mp4')},timeout=60)
 api={'status_code':r.status_code,'response':r.json()}
except Exception as e:api={'error':str(e)}
save(out/'api-upload.json',api)
# Frame contact sheet: real source / opaque / natural at evenly spaced times.
rows=[]
for idx in [0,40,80,120]:
 ims=[]
 for name in ['original','opaque','natural']:
  cap=cv2.VideoCapture(str(clip if name=='original' else out/(name+'.mp4')));cap.set(1,idx);ok,f=cap.read();cap.release()
  if ok:ims.append(cv2.resize(f,(480,270)))
 if len(ims)==3:rows.append(np.hstack(ims))
cv2.imwrite(str(out/'comparison.jpg'),np.vstack(rows))
report={'source':'DSText V2 Video_170_7_0; real handheld store footage, no synthetic additions','publisher':'https://zenodo.org/records/10010840','archive_md5':hashlib.md5((root/'split_1.zip').read_bytes()).hexdigest(),'frames':len(frames),'cloud_calls':0,'api_cost_usd':0,'local_ocr_target_detected_frames':len(regions),'tracking_geometry_frames':sum(g.corners is not None for g in geometry),'dataset_quad_iou_mean':float(np.mean(ious)) if ious else None,'dataset_quad_compared_frames':len(ious),'natural_render':{'natural_frames':surface.report()['natural_frames'],'fallback_frames':surface.report()['fallback_frames']},'independent_target_ocr':reviews,'core_renderer_error':engine_error,'api_upload':api,'visual_quality':quality_review(clip,out/'natural.mp4',tl),'elapsed_s':time.monotonic()-started,'limitations':['Selected product label is not a sensitive phone/plate; no privacy classification claim','One manual initial quadrilateral and selected OCR target; not autonomous surface discovery','Only one real camera scene; labels used after tracking for IoU','Silent dataset: spoken-phone recognition, audio mute, end-to-end API repair are NOT TESTED','No new Meta detection/tracking calls; local CV components only','Dataset footage remains private; redistribution rights not established']}
save(out/'report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='visual_quality'},indent=2))
