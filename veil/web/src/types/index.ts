/**
 * VEIL Frontend Type Contracts
 * Mirrors veil.core.models, veil.core.natural and recorded demonstration artifacts.
 */

export type FrameBox = [x1: number, y1: number, x2: number, y2: number];

export interface FrameRegion {
  frame: number;
  box: FrameBox;
  confidence?: number | null;
}

export type VisualCategory = 'face' | 'license_plate' | 'phone_number';

export interface VisualTrack {
  id: string;
  category: VisualCategory;
  source: string;
  action: 'cover' | 'blur';
  regions: FrameRegion[];
}

export interface AudioInterval {
  start_ms: number;
  end_ms: number;
  category: 'spoken_phone';
  source: string;
}

export interface Timeline {
  duration_ms: number;
  fps: number;
  width: number;
  height: number;
  visual_tracks: VisualTrack[];
  audio_intervals: AudioInterval[];
}

export type StageId = 'import' | 'detect' | 'redact' | 'verify' | 'repair' | 'export';

export type OperatingMode = 'real_dataset' | 'live_upload' | 'recorded';

export type RealClipId = 'vehicle_surface' | 'meta_blur' | 'tri_view';

export type RedactionStyle = 'natural' | 'opaque';

export type VideoVersion = 'source' | 'redacted' | 'repaired' | 'protected';

export type FindingStatus = 
  | 'detected' 
  | 'protected' 
  | 'unprotected_residual' 
  | 'repair_rejected' 
  | 'repair_completed';

export interface Finding {
  id: string;
  title: string;
  category: VisualCategory | 'spoken_phone';
  start_ms: number;
  end_ms: number;
  source: string;
  status: FindingStatus;
  statusLabel: string;
  description: string;
  confidence?: number | null;
  highlightBox?: FrameBox;
  trackId?: string;
  action?: 'cover' | 'blur' | 'natural_replacement';
}

export interface VerificationHeroSample {
  timestamp_s?: number;
  timestamp_label: string;
  imageUrl: string;
  status: string;
  modelReview?: string;
}

export interface VerificationHeroData {
  exposedTimestamp_ms: number;
  exposedTimestamp_label: string;
  frameIndex: number;
  frameImageUrl: string;
  returnedReason: string;
  exposedFieldLocation?: FrameBox;
  rejectedRepairImageUrl: string;
  rejectedRepairReason: string;
  correctedRepairImageUrl: string;
  sampledPasses: VerificationHeroSample[];
  scopeDisclaimer: string;
  time_ms?: number;
  timecode?: string;
  rule_violation?: string;
  exposed_value?: string;
  model_finding?: string;
  verifier_id?: string;
  target_box?: FrameBox;
  repair_action_summary?: string;
  evidence_quote?: string;
}

export interface RecordedReceipt {
  version?: string;
  job_id?: string;
  input_sha256: string;
  output_sha256: string;
  created_at?: string;
  duration_seconds?: number;
  visual_regions_covered?: number;
  audio_intervals_muted?: number;
  model_calls_estimated_cost_usd?: number;
  verified_samples_count?: number;
  limitations?: string[];
  timeline_source?: string;
  redaction_actions?: Record<string, 'cover' | 'blur'>;
  automatic_detection?: string;
  privacy_verification?: string;
  needs_human_review?: boolean;
  zero_leaks_guaranteed?: boolean;
  media_inspection?: {
    width: number;
    height: number;
    fps: number;
    duration_ms: number;
    has_audio: boolean;
    container_duration_s: number;
    decoded_frames: number;
    near_full_frame_black_frames: number[];
    utility_status: string;
    needs_human_review: boolean;
  };
  cloud_calls?: Array<{
    name: string;
    model: string;
    endpoint: string;
    status: string;
    cloud_transfer: string;
    latency_s: number;
    estimated_usd: number;
  }>;
  estimated_api_cost_usd?: number;
  billing_reconciled?: boolean;
}

export interface LocalJob {
  id: string;
  status: 'uploaded' | 'detecting' | 'detected' | 'rendering' | 'rendered' | 'verifying' | 'verified' | 'failed';
  media: {
    width: number;
    height: number;
    fps: number;
    duration_ms: number;
    has_audio: boolean;
    container_duration_s: number;
  };
  detection: string;
  verification: string;
  natural_verification?: string;
  needs_human_review: boolean;
  revision?: number;
}
