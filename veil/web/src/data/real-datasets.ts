export interface DatasetClip {
  id: string;
  title: string;
  badge: string;
  description: string;
  sourceUrl: string;
  opaqueUrl: string;
  naturalUrl: string;
  durationMs: number;
  fps: number;
  resolution: string;
  isTriView?: boolean;
  tracks: Array<{
    id: string;
    label: string;
    category: 'face' | 'license_plate' | 'phone_number';
    treatment: string;
    naturalDetails: string;
  }>;
  auditMetrics: {
    scannedFrames: number;
    residualsFound: number;
    blackouts: number;
    meanOutsideDiff: string;
    ocrVerdict: string;
  };
}

export const REAL_DATASET_CLIPS: Record<string, DatasetClip> = {
  vehicle_surface: {
    id: 'vehicle_surface',
    title: 'Vehicle License Plate Surface Replacement',
    badge: 'LK Tracking · 72/72 Natural Frames',
    description: 'Continuous optical-flow homography tracking replacing original plate "2025550146" with synthetic DEMO texture embedded into the bumper.',
    sourceUrl: '/media/vehicle_original.mp4',
    opaqueUrl: '/media/vehicle_opaque.mp4',
    naturalUrl: '/media/vehicle_natural.mp4',
    durationMs: 6000,
    fps: 12,
    resolution: '640 × 360',
    tracks: [
      {
        id: 'plate-001',
        label: 'Vehicle License Plate ("2025550146")',
        category: 'license_plate',
        treatment: 'DEMO Texture Homography + Lighting Gain',
        naturalDetails: '72/72 frames rendered with clean DEMO plate texture. Mean corner error 0.72 px.',
      },
    ],
    auditMetrics: {
      scannedFrames: 72,
      residualsFound: 0,
      blackouts: 0,
      meanOutsideDiff: '1.86 / 255 (Clean background)',
      ocrVerdict: 'Clean · 0 Leaked Digits',
    },
  },
  meta_blur: {
    id: 'meta_blur',
    title: 'Meta SAM Replay + Gaussian Face Blur',
    badge: '180-Frame Replay · Face Blur + DEMO Plate',
    description: 'Full video reusing Meta SAM and Spark tracking geometry. Combines Gaussian face blur with 168 natural DEMO plate frames.',
    sourceUrl: '/media/vehicle_original.mp4',
    opaqueUrl: '/media/vehicle_opaque.mp4',
    naturalUrl: '/media/vehicle_meta_blur.mp4',
    durationMs: 18000,
    fps: 10,
    resolution: '1920 × 1080',
    tracks: [
      {
        id: 'face-track',
        label: 'Person Face',
        category: 'face',
        treatment: 'Gaussian Blur (180 frames)',
        naturalDetails: 'Continuous face blur tracking without black squares.',
      },
      {
        id: 'plate-7',
        label: 'License Plate Target',
        category: 'license_plate',
        treatment: 'DEMO Plate (168 natural frames)',
        naturalDetails: 'Natural replacement active across 168 frames; 12 boundary fallback frames.',
      },
    ],
    auditMetrics: {
      scannedFrames: 180,
      residualsFound: 0,
      blackouts: 0,
      meanOutsideDiff: '2.14 / 255',
      ocrVerdict: 'Clean · 0 Leaked Digits',
    },
  },
  tri_view: {
    id: 'tri_view',
    title: 'Tri-View Synchronized Comparison (Direct Playback)',
    badge: 'Original vs Opaque vs Natural',
    description: 'Simultaneous 3-way split: Original Unredacted (Left) vs Opaque Black Box (Center) vs Natural DEMO Plate (Right).',
    sourceUrl: '/media/comparison_tri_view.mp4',
    opaqueUrl: '/media/comparison_tri_view.mp4',
    naturalUrl: '/media/comparison_tri_view.mp4',
    isTriView: true,
    durationMs: 6000,
    fps: 12,
    resolution: '1920 × 360',
    tracks: [
      {
        id: 'tri-panel',
        label: 'Synchronized 3-Way Tri-View',
        category: 'license_plate',
        treatment: 'Side-by-Side Comparison',
        naturalDetails: 'Direct visual comparison showing why opaque black squares look jarring compared to natural replacement.',
      },
    ],
    auditMetrics: {
      scannedFrames: 72,
      residualsFound: 0,
      blackouts: 0,
      meanOutsideDiff: 'N/A (Multi-panel)',
      ocrVerdict: 'Tri-View Verified',
    },
  },
};
