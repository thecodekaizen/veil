"""Evaluation-only check: reuse fixture labels AFTER rendering, never in API input."""
import argparse,json,subprocess,wave
from pathlib import Path
import cv2,numpy as np
from veil.providers.common import save
p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--truth',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
truth=json.loads(a.truth.read_text());cap=cv2.VideoCapture(str(a.video));covered=[]
for entry in truth['frames']:
    ok,frame=cap.read()
    if not ok:raise ValueError('Frame count shorter than truth')
    x,y,_,_=entry['printed_phone'];roi=frame[y+35:y+65,x+10:x+270]
    covered.append(float((roi.max(axis=2)<40).mean()))
extra,_=cap.read();cap.release()
if extra:raise ValueError('Frame count longer than truth')
wav=a.output.with_suffix('.wav')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(a.video),'-vn','-ac','1','-ar','24000','-c:a','pcm_s16le',str(wav)],check=True)
with wave.open(str(wav)) as stream:
    rate=stream.getframerate();samples=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(float)/32768
speech=samples[truth['speech_start_ms']*rate//1000:truth['speech_end_ms']*rate//1000]
if not speech.size:raise ValueError('Expected speech interval absent')
save(a.output,{'evaluation_only':True,'decoded_frames':len(covered),'printed_phone_black_coverage_min':min(covered),
    'printed_phone_frames_below_99pct':[i for i,v in enumerate(covered) if v<.99],
    'known_spoken_number_rms':float(np.sqrt(np.mean(speech**2))),'known_spoken_number_max_absolute':float(np.abs(speech).max()),
    'limits':['Reused synthetic fixture; no new independent case','Face de-identification and new plate replacement not scored by this black-pixel metric']})
