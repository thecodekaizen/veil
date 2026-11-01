import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { C } from "../theme";

/** Near-black canvas with a slow-drifting warm glow and film grain. */
export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(60% 55% at ${interpolate(frame, [0, 6000], [20, 80])}% ${interpolate(frame, [0, 6000], [15, 45])}%, rgba(232,176,74,0.10), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: "radial-gradient(70% 60% at 85% 100%, rgba(80,110,160,0.10), transparent 70%)",
        }}
      />
      <AbsoluteFill style={{ opacity: 0.07, mixBlendMode: "overlay" }}>
        <svg width="100%" height="100%">
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 8} />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
