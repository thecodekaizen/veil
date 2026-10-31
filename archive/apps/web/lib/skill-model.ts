/** The small shared contract that Teach, Do, and Simulate will all use. */
export type SkillObject = {
  id: string;
  name: string;
  color: string;
  shape: "base" | "washer" | "bracket" | "bolt" | "component";
  visualDescription?: string;
};

export type SkillEvidence = { startSeconds: number; endSeconds: number; observation: string };

export type SkillConstraint =
  | {
    id: string;
    description: string;
    status: "proposed";
    source: "model-hypothesis";
    evidence?: SkillEvidence[];
  }
  | {
    id: string;
    description: string;
    requiredState: string;
    status: "confirmed";
    source: "expert-narration" | "repeatable-observation" | "human-confirmation" | "illustrative-fixture";
    evidence?: SkillEvidence[];
  };

export type SkillAction = {
  id: string;
  label: string;
  objectIds: string[];
  constraints: SkillConstraint[];
  produces: string[];
  /** Candidate states seen in one trace; these are not universal constraints. */
  fromState?: string;
  toState?: string;
  explanation: string;
  recovery: string;
  evidence?: SkillEvidence[];
};

export type SkillModel = {
  id: string;
  title: string;
  status: "illustrative-fixture" | "candidate-needs-review" | "learned-from-demonstration";
  states?: { id: string; label: string; observableFacts?: string[] }[];
  objects: SkillObject[];
  initialState: string[];
  actions: SkillAction[];
};

/**
 * A transparent interaction fixture, not a claim that this procedure has been
 * learned from video. Replace it with the model returned by Teach later.
 */
export const SAMPLE_SKILL: SkillModel = {
  id: "stacked-mount-fixture",
  title: "Stacked mount assembly",
  status: "illustrative-fixture",
  objects: [
    { id: "base", name: "Mounting base", color: "stone", shape: "base" },
    { id: "washer", name: "Spacer ring", color: "amber", shape: "washer" },
    { id: "bracket", name: "Support bracket", color: "blue", shape: "bracket" },
    { id: "bolt", name: "Fastener", color: "copper", shape: "bolt" },
  ],
  initialState: ["base_ready", "washer_available", "bracket_available", "bolt_available"],
  actions: [
    {
      id: "place-washer",
      label: "Place spacer ring",
      objectIds: ["washer"],
      constraints: [
        { id: "base-ready-for-washer", description: "The base is ready.", requiredState: "base_ready", status: "confirmed", source: "illustrative-fixture" },
        { id: "washer-available", description: "The spacer ring is available.", requiredState: "washer_available", status: "confirmed", source: "illustrative-fixture" },
      ],
      produces: ["washer_seated"],
      explanation: "The spacer sits on the base before the bracket covers the joint.",
      recovery: "Lift the bracket, seat the spacer on the base, then replace the bracket.",
    },
    {
      id: "place-bracket",
      label: "Mount support bracket",
      objectIds: ["bracket", "washer"],
      constraints: [
        { id: "base-ready-for-bracket", description: "The base is ready.", requiredState: "base_ready", status: "confirmed", source: "illustrative-fixture" },
        { id: "bracket-available", description: "The support bracket is available.", requiredState: "bracket_available", status: "confirmed", source: "illustrative-fixture" },
        { id: "washer-before-bracket", description: "The spacer ring is seated first.", requiredState: "washer_seated", status: "confirmed", source: "illustrative-fixture" },
      ],
      produces: ["bracket_mounted"],
      explanation: "The bracket depends on the spacer being seated first.",
      recovery: "Remove the bracket, place the spacer ring, then mount the bracket again.",
    },
    {
      id: "insert-bolt",
      label: "Insert fastener",
      objectIds: ["bolt", "bracket"],
      constraints: [
        { id: "bracket-before-fastener", description: "The bracket is mounted first.", requiredState: "bracket_mounted", status: "confirmed", source: "illustrative-fixture" },
        { id: "fastener-available", description: "The fastener is available.", requiredState: "bolt_available", status: "confirmed", source: "illustrative-fixture" },
      ],
      produces: ["fastener_inserted"],
      explanation: "The fastener locks the mounted bracket to the base.",
      recovery: "Back out the fastener, confirm the spacer is seated, then reassemble in order.",
    },
  ],
};
