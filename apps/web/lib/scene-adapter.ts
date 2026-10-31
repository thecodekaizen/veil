import type { SkillModel } from "./skill-model";

/**
 * A scene adapter maps semantic object IDs from the Skill Model to visual
 * presentation data. It does NOT contain process logic — that stays in the
 * Skill Model and simulation engine.
 *
 * Geometry here is presentation with disclosed provenance. It is not a claim
 * that the model learned physical shapes or spatial relationships.
 */

export type ObjectVisual = {
  /** Matches SkillObject.id */
  id: string;
  /** CSS color or short token */
  fill: string;
  /** Display shape hint — used for CSS-driven rendering */
  shape:
    | "block"
    | "plate"
    | "bracket"
    | "pin"
    | "ring"
    | "generic"
    | "lego-cockpit"
    | "lego-wing"
    | "lego-strut"
    | "lego-stud"
    | "lego-plate"
    | "lego-brick"
    | "simready-mesh";
  /** Approx relative width in scene units (0–1 scale, largest object = 1) */
  width: number;
  /** Approx relative height in scene units */
  height: number;
  /** Optional asset image URL or thumbnail */
  assetUrl?: string;
};

export type StateVisual = {
  /** Matches a declared state ID */
  stateId: string;
  /** Which objects are visible/active in this state */
  activeObjectIds: string[];
  /** CSS layout hint — how objects relate spatially in this state */
  layout: "stacked" | "side-by-side" | "connected" | "separated";
};

export type SceneAdapter = {
  /** Human-readable name of this scene mapping */
  name: string;
  /** Where the geometry came from (transparency requirement D.4) */
  provenance:
    | "hand-authored-fixture"
    | "task-specific-mapping"
    | "placeholder-only"
    | "simready-asset-nvidia";
  /** License and attribution notice if external asset is used */
  licenseNotice?: string;
  /** Source dataset or asset ID */
  assetReference?: string;
  /** Per-object visual data; keyed by object ID for lookup */
  objects: Map<string, ObjectVisual>;
  /** Per-state visual arrangement hints */
  states: Map<string, StateVisual>;
  /** Object IDs that have no visual mapping — rendered as neutral placeholders */
  unmappedObjectIds: string[];
};

/** Detect whether a model represents the LEGO task (e.g. 30727 TIE or wing assemblies). */
export function isLegoTask(model: SkillModel): boolean {
  const text = `${model.id} ${model.title} ${model.objects.map((o) => `${o.id} ${o.name}`).join(" ")}`.toLowerCase();
  return (
    text.includes("lego") ||
    text.includes("30727") ||
    text.includes("tie") ||
    text.includes("cockpit") ||
    text.includes("wing")
  );
}

/** Detect whether a model represents a SimReady task (e.g. engine mount assembly). */
export function isSimReadyTask(model: SkillModel): boolean {
  const text = `${model.id} ${model.title} ${model.objects.map((o) => `${o.id} ${o.name}`).join(" ")}`.toLowerCase();
  return (
    text.includes("simready") ||
    text.includes("engine_mount") ||
    text.includes("enginemount") ||
    text.includes("engine-mount")
  );
}

/** Build a scene adapter from a Skill Model.
 *  Uses task-specific LEGO geometry for LEGO models, SimReady geometry for engine mount models,
 *  fixture geometry for sample fixture, or neutral placeholders otherwise. */
export function buildSceneAdapter(model: SkillModel): SceneAdapter {
  if (isSimReadyTask(model)) {
    return buildSimReadyScene(model);
  }
  if (model.status === "illustrative-fixture") {
    return buildFixtureScene(model);
  }
  if (isLegoTask(model)) {
    return buildLegoScene(model);
  }
  return buildPlaceholderScene(model);
}

/** Build a scene adapter using NVIDIA SimReady asset presentation data.
 *  Discloses CC-BY-4.0 provenance and maps semantic parts to visual props.
 *  Crucially, contains ZERO procedural logic, preconditions, or transition rules. */
export function buildSimReadyScene(model: SkillModel): SceneAdapter {
  const objects = new Map<string, ObjectVisual>();

  const palette: Record<string, string> = {
    stone: "#7a8793",
    blue: "#4a7a96",
    black: "#22262a",
    copper: "#b36842",
    amber: "#c49a45",
  };

  for (const obj of model.objects) {
    const text = `${obj.id} ${obj.name}`.toLowerCase();
    let width = 0.6;
    let height = 0.5;

    if (text.includes("base") || text.includes("housing")) {
      width = 0.9;
      height = 0.4;
    } else if (text.includes("bracket") || text.includes("arm")) {
      width = 0.75;
      height = 0.6;
    } else if (text.includes("damper") || text.includes("rubber") || text.includes("washer")) {
      width = 0.4;
      height = 0.4;
    } else if (text.includes("bolt") || text.includes("fastener") || text.includes("bushing")) {
      width = 0.3;
      height = 0.5;
    }

    objects.set(obj.id, {
      id: obj.id,
      fill: palette[obj.color] ?? "#6c7a89",
      shape: "simready-mesh",
      width,
      height,
      assetUrl: "/assets/simready/engineComponent_engine_mount_a01.png",
    });
  }

  const states = new Map<string, StateVisual>();
  for (const state of model.states ?? []) {
    const text = `${state.id} ${state.label}`.toLowerCase();
    const related = model.actions
      .filter((a) => a.toState === state.id || a.fromState === state.id)
      .flatMap((a) => a.objectIds)
      .filter((id) => id !== "unknown");

    let layout: StateVisual["layout"] = "connected";
    if (
      text.includes("loose") ||
      text.includes("standby") ||
      text.includes("initial") ||
      text.includes("separated") ||
      text.includes("ready")
    ) {
      layout = "separated";
    } else if (text.includes("stack") || text.includes("mount") || text.includes("attach")) {
      layout = "stacked";
    }

    states.set(state.id, {
      stateId: state.id,
      activeObjectIds: related.length > 0 ? [...new Set(related)] : model.objects.map((o) => o.id),
      layout,
    });
  }

  return {
    name: model.title,
    provenance: "simready-asset-nvidia",
    licenseNotice: "CC-BY-4.0 (NVIDIA Corporation)",
    assetReference: "nvidia/simready-assets:engineComponent_engine_mount_a01",
    objects,
    states,
    unmappedObjectIds: model.objects
      .filter((obj) => !objects.has(obj.id))
      .map((obj) => obj.id),
  };
}

function buildLegoScene(model: SkillModel): SceneAdapter {
  const objects = new Map<string, ObjectVisual>();

  for (const obj of model.objects) {
    const text = `${obj.id} ${obj.name}`.toLowerCase();
    let shape: ObjectVisual["shape"] = "lego-brick";
    let fill = "#5b6672";
    let width = 0.5;
    let height = 0.4;

    if (text.includes("cockpit") || text.includes("fuselage") || text.includes("core")) {
      shape = "lego-cockpit";
      fill = "#414b55";
      width = 0.8;
      height = 0.75;
    } else if (text.includes("strut") || text.includes("bracket") || text.includes("pylon")) {
      shape = "lego-strut";
      fill = "#737f8d";
      width = 0.45;
      height = 0.35;
    } else if (text.includes("stud") || text.includes("pin") || text.includes("connector")) {
      shape = "lego-stud";
      fill = "#93a0af";
      width = 0.25;
      height = 0.25;
    } else if (text.includes("wing") || text.includes("panel")) {
      shape = "lego-wing";
      fill = "#21262d";
      width = 0.95;
      height = 0.9;
    } else if (text.includes("plate") || text.includes("tile") || text.includes("base")) {
      shape = "lego-plate";
      fill = "#525e6b";
      width = 0.85;
      height = 0.25;
    }

    objects.set(obj.id, {
      id: obj.id,
      fill,
      shape,
      width,
      height,
    });
  }

  const states = new Map<string, StateVisual>();
  for (const state of model.states ?? []) {
    const text = `${state.id} ${state.label}`.toLowerCase();
    const related = model.actions
      .filter((a) => a.toState === state.id || a.fromState === state.id)
      .flatMap((a) => a.objectIds)
      .filter((id) => id !== "unknown");

    let layout: StateVisual["layout"] = "connected";
    if (text.includes("detach") || text.includes("loose") || text.includes("initial") || text.includes("separated")) {
      layout = "separated";
    } else if (text.includes("stack")) {
      layout = "stacked";
    }

    states.set(state.id, {
      stateId: state.id,
      activeObjectIds: related.length > 0 ? [...new Set(related)] : model.objects.map((o) => o.id),
      layout,
    });
  }

  return {
    name: model.title,
    provenance: "task-specific-mapping",
    objects,
    states,
    unmappedObjectIds: model.objects
      .filter((obj) => !objects.has(obj.id))
      .map((obj) => obj.id),
  };
}

function buildFixtureScene(model: SkillModel): SceneAdapter {
  const palette: Record<string, string> = {
    stone: "#a1a1a1", amber: "#d4a853", blue: "#5b8fb4", copper: "#c08050",
  };
  const shapeMap: Record<string, ObjectVisual["shape"]> = {
    base: "plate", washer: "ring", bracket: "bracket", bolt: "pin", component: "generic",
  };

  const objects = new Map<string, ObjectVisual>();
  for (const obj of model.objects) {
    objects.set(obj.id, {
      id: obj.id,
      fill: palette[obj.color] ?? "#888",
      shape: shapeMap[obj.shape] ?? "generic",
      width: obj.shape === "base" ? 1 : obj.shape === "bracket" ? 0.7 : 0.4,
      height: obj.shape === "base" ? 0.2 : obj.shape === "bracket" ? 0.5 : 0.3,
    });
  }

  const states = new Map<string, StateVisual>();
  // Derive state visuals from what each state means in the fixture
  for (const state of model.states ?? []) {
    const active = model.objects
      .filter((obj) => state.id.includes(obj.id) || model.actions.some(
        (a) => (a.toState === state.id || a.fromState === state.id) && a.objectIds.includes(obj.id),
      ))
      .map((obj) => obj.id);
    states.set(state.id, {
      stateId: state.id,
      activeObjectIds: active.length > 0 ? active : model.objects.map((o) => o.id),
      layout: state.id.includes("mounted") || state.id.includes("seated") || state.id.includes("inserted") ? "stacked" : "separated",
    });
  }

  return {
    name: model.title,
    provenance: "hand-authored-fixture",
    objects,
    states,
    unmappedObjectIds: [],
  };
}

function buildPlaceholderScene(model: SkillModel): SceneAdapter {
  const colors = ["#7aab7a", "#8a9fc8", "#c8a86a", "#c87a7a", "#9a7ac8", "#7ac8c8"];
  const objects = new Map<string, ObjectVisual>();
  for (const [index, obj] of model.objects.entries()) {
    objects.set(obj.id, {
      id: obj.id,
      fill: colors[index % colors.length],
      shape: "generic",
      width: 0.5,
      height: 0.3,
    });
  }

  const states = new Map<string, StateVisual>();
  for (const state of model.states ?? []) {
    const related = model.actions
      .filter((a) => a.toState === state.id || a.fromState === state.id)
      .flatMap((a) => a.objectIds)
      .filter((id) => id !== "unknown");
    states.set(state.id, {
      stateId: state.id,
      activeObjectIds: related.length > 0 ? [...new Set(related)] : model.objects.map((o) => o.id),
      layout: "side-by-side",
    });
  }

  return {
    name: model.title,
    provenance: "placeholder-only",
    objects,
    states,
    unmappedObjectIds: model.objects
      .filter((obj) => !objects.has(obj.id))
      .map((obj) => obj.id),
  };
}

/** Get the set of active object IDs for a given set of state IDs */
export function activeObjectsForState(adapter: SceneAdapter, stateIds: string[]): string[] {
  const active = new Set<string>();
  for (const stateId of stateIds) {
    const sv = adapter.states.get(stateId);
    if (sv) {
      for (const id of sv.activeObjectIds) active.add(id);
    }
  }
  return [...active];
}

/** Determine the dominant layout for a combined set of states */
export function layoutForState(adapter: SceneAdapter, stateIds: string[]): StateVisual["layout"] {
  for (const stateId of stateIds) {
    const sv = adapter.states.get(stateId);
    if (sv && sv.layout !== "separated") return sv.layout;
  }
  return "separated";
}
