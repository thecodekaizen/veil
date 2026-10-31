"""SAM wire format stays at this adapter boundary."""
import asyncio,base64
from dataclasses import asdict
from pathlib import Path
from meta_sam_parser import parse_responses_stream,image_segmentation_format,video_segmentation_format,decode_mask_to_raster
from .common import save

async def _parse(events,video):
 async def source():
  try:
   for event in events:yield event
  finally:events.close()
 return await parse_responses_stream(source(),video_segmentation_format() if video else image_segmentation_format()).final_result()

def segment(client,ledger,root,name,concept,*,image=None,file_id=None,frame_count=180):
 video=file_id is not None
 media={'type':'input_video','file_id':file_id} if video else {'type':'input_image','image_url':'data:image/jpeg;base64,'+base64.b64encode(Path(image).read_bytes()).decode()}
 start=ledger.begin(name,'sam-3.1','/v1/responses', 'Authorized job MP4 referenced by file ID' if video else 'Authorized JPEG frame')
 try:
  events=client.responses.create(model='sam-3.1',input=[{'type':'message','role':'user','content':[{'type':'input_text','text':concept},media]}],stream=True,metadata={'mask_encoding':'one_bit'})
  result=asyncio.run(_parse(events,video))
  (root/f'{name}-raw.txt').write_text(result.raw_output)
  if result.outcome.status!='completed':raise ValueError('SAM stream did not complete')
  rows=[]
  for record in result.records:
   if record.kind=='box':
    rows.append({'frame':record.frame.frame_index if record.frame else 0,'track_id':record.object_id,
                 'box':[record.left,record.top,record.right,record.bottom],'confidence':record.confidence})
   if record.kind=='mask':
    # Decode to establish real usable masks, then store compact metadata rather than provider types.
    raster=decode_mask_to_raster(record.mask)
    if len(raster)!=record.mask.width*record.mask.height:raise ValueError('Mask raster size mismatch')
  mask_count=sum(r.kind=='mask' for r in result.records)
  save(root/f'{name}.json',{'concept':concept,'video':video,'regions':rows,'masks_decoded':mask_count,
       'diagnostics':[d.code for d in result.diagnostics]})
  estimated=.0002*max(50,frame_count) if video else .0025
  ledger.finish(name,start,regions=len(rows),masks_decoded=mask_count,estimated_usd=estimated,
                cost_basis=f'{frame_count} submitted video frames at published rate, provisional until provider usage available' if video else 'published per-image rate')
  return rows
 except Exception as exc:ledger.fail(name,start,exc);raise


def segment_masks(client, ledger, root, name, concept, *, file_id, frame_count):
    """Like segment(), but also keeps each decoded mask (1-bit crop + bounds) per (track, frame).
    Returns {track_id: {frame: {'box': [l,t,r,b], 'mask': (w, h, bytes, bounds) | None}}}."""
    import numpy as np
    start = ledger.begin(name, 'sam-3.1', '/v1/responses', 'Authorized job MP4 referenced by file ID')
    try:
        events = client.responses.create(model='sam-3.1', input=[{'type': 'message', 'role': 'user', 'content': [
            {'type': 'input_text', 'text': concept}, {'type': 'input_video', 'file_id': file_id}]}],
            stream=True, metadata={'mask_encoding': 'one_bit'})
        result = asyncio.run(_parse(events, True))
        (root / f'{name}-raw.txt').write_text(result.raw_output)
        if result.outcome.status != 'completed':
            raise ValueError('SAM stream did not complete')
        tracks = {}
        masks = 0
        for record in result.records:
            frame = record.frame.frame_index if record.frame else 0
            entry = tracks.setdefault(str(record.object_id), {}).setdefault(frame, {'box': None, 'mask': None})
            if record.kind == 'box':
                entry['box'] = [record.left, record.top, record.right, record.bottom]
            elif record.kind == 'mask':
                raster = decode_mask_to_raster(record.mask)
                if len(raster) != record.mask.width * record.mask.height:
                    raise ValueError('Mask raster size mismatch')
                bits = np.frombuffer(raster, dtype=np.uint8) > 0
                b = record.bounds
                entry['mask'] = (record.mask.width, record.mask.height, np.packbits(bits).tobytes(),
                                 (b.left, b.top, b.right, b.bottom))
                masks += 1
        ledger.finish(name, start, tracks=len(tracks), masks_decoded=masks, estimated_usd=.0002 * max(50, frame_count),
                      cost_basis=f'{frame_count} submitted video frames at published rate, provisional')
        return tracks
    except Exception as exc:
        ledger.fail(name, start, exc)
        raise
