# SimReady Asset Integration, License, and Conversion Report

**Asset Source:** [NVIDIA SimReady Assets on Hugging Face](https://huggingface.co/datasets/nvidia/simready-assets)  
**Evaluated Asset:** `engineComponent_engine_mount_a01`  
**Evaluation Target:** SHOWME Interactive Simulation Surface (`apps/web`)  
**Architecture Rule:** Complete decoupling of visual/geometric representation from learned procedural rules.

---

## 1. Asset Selection & Inspection

We inspected the NVIDIA SimReady Assets repository on Hugging Face (`nvidia/simready-assets`, containing over 1,000 OEM-curated simulation-ready props) and selected `engineComponent_engine_mount_a01`:

- **Path:** `engineComponent_engine_mount_a01`
- **Relevance to SHOWME:** Directly aligns with our 4–6 piece mechanical assembly scenario (concept motor-mount assembly referenced in `docs/SHOWME_SIMULATION_DESIGN.md` and mockups).
- **Physical Hierarchy:** Comprises a rigid mounting base/casing, rubber vibration damping core, steel support bracket/arm, and fastener sleeve bushing.
- **Payload Structure in Repo:**
  - `simready_usd/sm_engineComponent_engine_mount_a01_01.usd`: Root composition USD stage.
  - `simready_usd/payloads/base.usda`: SimReady metadata, engine variant switches.
  - `simready_usd/payloads/instances.usda`: Mesh definitions, transform hierarchies, and visual material bindings.
  - `simready_usd/payloads/instances_physx.usda` / `instances_mujoco.usda` / `instances_newton.usda`: Physics solver configurations (SDF collision approximations, center of mass, diagonal inertia tensor, mass = 0.563 kg).
  - `simready_usd/source_assets/`: NVIDIA Material Definition Language (MDL) files (`OmniPBR.mdl`, `OmniPBRBase.mdl`) and PBR texture channels (Albedo `_alb.png`, Normal `_nor.png`, Occlusion/Roughness/Metallic `_orm.png`).
  - `.metadata/`: Conformance reports (`Package@1.0.0.json`), Bill of Materials (`bom.json`), packaging manifest, and license text.

---

## 2. License Documentation

- **License:** **Creative Commons Attribution 4.0 International (CC-BY-4.0)**
- **Licensor:** NVIDIA Corporation
- **License File:** `engineComponent_engine_mount_a01/.metadata/LICENSE.txt`
- **Package Manifest:** `com.nvidia.simready.packaging.json` (`"license": "CC-BY-4.0"`)
- **Key Terms & Obligations:**
  1. **Attribution:** We must give appropriate credit to NVIDIA ("NVIDIA SimReady Assets", CC-BY-4.0), provide a link to the license, and indicate if changes were made.
  2. **Freedom to Share and Adapt:** CC-BY-4.0 permits copying, redistributing, remixing, transforming, and building upon the material for any purpose, including commercial applications.
  3. **No Additional Restrictions:** We may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.
  4. **Attribution in SHOWME:** Surface provenance is tracked in the Scene Adapter (`provenance: "simready-asset-nvidia"`) and rendered in the simulation UI with explicit attribution notice.

---

## 3. Conversion Needs for Browser Simulation

SimReady assets are packaged for NVIDIA Omniverse, Isaac Sim, and desktop robotics simulators. They cannot be directly dropped into a web browser application without conversion:

| Pipeline Dimension | SimReady Native Format | Web / SHOWME Target Format | Conversion Requirements |
|---|---|---|---|
| **File Format & Scene Graph** | OpenUSD (`.usd`, `.usda`, `.usdc`) with layered payloads and references | glTF 2.0 (`.glb`) or optimized vector/raster projection (SVG / WebP) | Convert USD stage to standard binary glTF via `usd2gltf`, Apple `usdzconvert`, or headless Blender export pipeline. Flatten USD payload composition into a single node hierarchy. |
| **Materials & Shaders** | NVIDIA MDL (`OmniPBR.mdl`) | glTF PBR Metallic-Roughness | Map Omniverse MDL properties to standard glTF PBR: `_alb.png` to `baseColorTexture`, `_nor.png` to `normalTexture`. |
| **Texture Packing** | Composite `_orm.png` texture (Red: Occlusion, Green: Roughness, Blue: Metallic) | Standard glTF ORM packing | SimReady's ORM channel order matches glTF 2.0 specification (R=AO, G=Roughness, B=Metalness). Textures must be downscaled (from 2K/4K to 512px/1024px) and compressed using Basis Universal / KTX2 or WebP. |
| **Physics & Collision Tags** | `physics:approximation = "sdf"`, `physics:mass`, `physics:diagonalInertia`, PhysX/MuJoCo schemas | **Decoupled / Stripped** | SHOWME does not run an arbitrary physics engine. Physical dynamics metadata must be omitted so it does not interfere with procedural verification. |
| **LOD & Mesh Density** | High-density CAD tessellation | Decimated real-time mesh | Run mesh simplification (Draco compression or meshoptimizer) to bring download payload under 2 MB for browser sessions. |

---

## 4. Separation of Geometry from Learned Procedure Rules

### The Architectural Boundary

```text
┌─────────────────────────────────────────────────────────────┐
│                       SKILL MODEL                           │
│  • Objects: { id: "bracket", name: "Support Bracket" }      │
│  • States: "base_ready" ──> "bracket_mounted"               │
│  • Actions: { id: "place_bracket", preconditions: [...] }   │
│  • Provenance: demonstration timestamps, human review       │
└──────────────────────────────┬──────────────────────────────┘
                               │ (semantic IDs only)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      SCENE ADAPTER                          │
│  • Maps object ID "bracket" -> visual asset (SimReady)      │
│  • Visual layout & transforms (stacked, separated)          │
│  • Provenance: "simready-asset-nvidia" (CC-BY-4.0)          │
│  • ZERO process logic, ZERO preconditions, ZERO constraints │
└─────────────────────────────────────────────────────────────┘
```

### Why Geometry Must NOT Dictate Procedure Rules:
1. **Preventing Hallucinated Physics:** A 3D bounding box or mesh collision cannot prove whether a part *must* be installed before another in a real human task. Procedural prerequisites must come from repeatable demonstration evidence, expert narration, or human confirmation—never from 3D mesh collisions.
2. **Model Portability:** The learner might assemble a real physical object on camera under different viewpoints. If the procedure is tied to exact 3D vertex coordinates, real-world camera tracking breaks.
3. **Inspectable Uncertainty:** If an alternative order was unobserved in the demonstration, SHOWME must report that the transition is *unestablished by evidence*, rather than falsely claiming the physical geometry makes it "impossible."
4. **Deterministic Simulation:** The simulator engine (`simulate.ts`) steps through the Skill Model's state transitions deterministically. The scene adapter acts strictly as a presentation projector for the resulting state.
