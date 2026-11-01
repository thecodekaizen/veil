import { loadFont as loadDisplay } from "@remotion/google-fonts/Fraunces";
import { loadFont as loadBody } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { Easing } from "remotion";
import timeline from "./data/timeline.json";

export const display = loadDisplay("normal", { weights: ["600", "700"], subsets: ["latin"] }).fontFamily;
export const body = loadBody("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] }).fontFamily;
export const mono = loadMono("normal", { weights: ["400", "600"], subsets: ["latin"] }).fontFamily;

// Same palette as the Veil web UI (veil/web/src/demo/demo.css).
export const C = {
  bg: "#0B0D10",
  panel: "#14171C",
  line: "#262B34",
  text: "#F2EFE8",
  dim: "#9A968D",
  amber: "#E8B04A",
  red: "#E66B5B",
  green: "#6FCF8F",
};

export const EASE = Easing.bezier(0.16, 1, 0.3, 1); // ease-out-expo-ish
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export type Timeline = typeof timeline;
export const T = timeline;
export const FPS = timeline.fps;

/** Frame where a script line starts (visual leads audio by 3 frames). */
export const at = (id: string) => (T.lines as Record<string, { s: number; e: number }>)[id].s - 3;
export const end = (id: string) => (T.lines as Record<string, { s: number; e: number }>)[id].e;
/** Frame where an emphasis word of a line is spoken. */
export const emph = (id: string, word: string) =>
  (T.emph as Record<string, Record<string, number>>)[id]?.[word] ?? at(id);
