import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/scene-adapter.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const {
  buildSceneAdapter,
  activeObjectsForState,
  layoutForState,
  isSimReadyTask,
  buildSimReadyScene,
} = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("builds fixture scene with hand-authored-fixture provenance", () => {
  const model = {
    id: "stacked-mount-fixture",
    title: "Stacked mount assembly",
    status: "illustrative-fixture",
    objects: [
      { id: "base", name: "Mounting base", color: "stone", shape: "base" },
      { id: "washer", name: "Spacer ring", color: "amber", shape: "washer" },
    ],
    initialState: ["base_ready", "washer_available"],
    actions: [],
  };

  const adapter = buildSceneAdapter(model);
  assert.equal(adapter.provenance, "hand-authored-fixture");
  assert.equal(adapter.objects.get("base").shape, "plate");
  assert.equal(adapter.objects.get("washer").shape, "ring");
  assert.equal(adapter.unmappedObjectIds.length, 0);
});

test("builds placeholder scene for non-lego learned models and discloses placeholder-only provenance", () => {
  const model = {
    id: "learned-process",
    title: "Learned task",
    status: "learned-from-demonstration",
    objects: [
      { id: "sensor", name: "Temperature sensor", color: "blue", shape: "component" },
      { id: "harness", name: "Wire harness", color: "amber", shape: "component" },
    ],
    initialState: ["initial"],
    states: [{ id: "step1", label: "Sensor attached" }],
    actions: [
      { id: "attach", label: "Attach sensor", objectIds: ["sensor"], produces: ["step1"], fromState: "initial", toState: "step1" },
    ],
  };

  const adapter = buildSceneAdapter(model);
  assert.equal(adapter.provenance, "placeholder-only");
  assert.equal(adapter.objects.has("sensor"), true);
  assert.equal(adapter.objects.has("harness"), true);
  assert.equal(adapter.objects.get("sensor").shape, "generic");
});

test("builds task-specific scene for LEGO models and discloses task-specific-mapping provenance", () => {
  const legoModel = {
    id: "lego-30727",
    title: "LEGO 30727 TIE Fighter Assembly",
    status: "learned-from-demonstration",
    objects: [
      { id: "cockpit_core", name: "Cockpit core fuselage", color: "stone", shape: "component" },
      { id: "left_wing", name: "Left solar wing panel", color: "stone", shape: "component" },
      { id: "wing_strut", name: "Wing connector strut", color: "stone", shape: "component" },
    ],
    initialState: ["parts_separated"],
    states: [
      { id: "parts_separated", label: "Parts loose on work surface" },
      { id: "wing_mounted", label: "Wing mounted to cockpit" },
    ],
    actions: [
      { id: "mount-wing", label: "Mount wing", objectIds: ["left_wing", "wing_strut"], produces: ["wing_mounted"], fromState: "parts_separated", toState: "wing_mounted" },
    ],
  };

  const adapter = buildSceneAdapter(legoModel);
  assert.equal(adapter.provenance, "task-specific-mapping");
  assert.equal(adapter.objects.get("cockpit_core").shape, "lego-cockpit");
  assert.equal(adapter.objects.get("left_wing").shape, "lego-wing");
  assert.equal(adapter.objects.get("wing_strut").shape, "lego-strut");
  assert.equal(adapter.states.get("parts_separated").layout, "separated");
  assert.equal(adapter.states.get("wing_mounted").layout, "connected");
});

test("activeObjectsForState identifies active objects according to state visual mapping", () => {
  const model = {
    id: "learned-process",
    title: "Learned task",
    status: "learned-from-demonstration",
    objects: [
      { id: "wing", name: "Wing", color: "blue", shape: "component" },
      { id: "base", name: "Base", color: "stone", shape: "component" },
    ],
    initialState: ["s0"],
    states: [{ id: "s1", label: "Wing joined" }],
    actions: [
      { id: "a1", label: "Join wing", objectIds: ["wing"], produces: ["s1"], fromState: "s0", toState: "s1" },
    ],
  };

  const adapter = buildSceneAdapter(model);
  const active = activeObjectsForState(adapter, ["s1"]);
  assert.deepEqual(active, ["wing"]);
});

test("layoutForState returns separated when no states match or layouts are separated", () => {
  const model = {
    id: "learned-process",
    title: "Learned task",
    status: "learned-from-demonstration",
    objects: [{ id: "o1", name: "Obj 1", color: "blue", shape: "component" }],
    initialState: ["s0"],
    states: [{ id: "s0", label: "Start" }],
    actions: [],
  };

  const adapter = buildSceneAdapter(model);
  assert.equal(layoutForState(adapter, ["nonexistent"]), "separated");
});

test("detects SimReady task and builds scene adapter with CC-BY-4.0 provenance and decoupled geometry", () => {
  const model = {
    id: "engineComponent_engine_mount_a01",
    title: "Engine Mount Subassembly",
    status: "learned-from-demonstration",
    objects: [
      { id: "base", name: "Mounting Base", color: "stone", shape: "base" },
      { id: "bracket", name: "Support Bracket", color: "blue", shape: "bracket" },
      { id: "damper", name: "Rubber Vibration Damper", color: "black", shape: "washer" },
      { id: "fastener", name: "Bushing Bolt", color: "copper", shape: "bolt" },
    ],
    initialState: ["base_ready", "bracket_ready"],
    states: [
      { id: "base_ready", label: "Base fixed to jig" },
      { id: "bracket_ready", label: "Bracket in standby" },
      { id: "bracket_attached", label: "Bracket attached to base" },
    ],
    actions: [
      {
        id: "attach-bracket",
        label: "Attach bracket",
        objectIds: ["bracket", "base"],
        fromState: "bracket_ready",
        toState: "bracket_attached",
        produces: ["bracket_attached"],
      },
    ],
  };

  assert.equal(isSimReadyTask(model), true);
  const adapter = buildSimReadyScene(model);
  assert.equal(adapter.provenance, "simready-asset-nvidia");
  assert.match(adapter.licenseNotice, /CC-BY-4.0/);
  assert.match(adapter.assetReference, /engineComponent_engine_mount_a01/);
  assert.equal(adapter.objects.get("bracket").shape, "simready-mesh");
  assert.equal(typeof adapter.objects.get("bracket").assetUrl, "string");

  // Geometry is purely presentation: adapter must NOT define or alter procedural rules
  assert.equal("actions" in adapter, false);
  assert.equal("preconditions" in adapter, false);
});
