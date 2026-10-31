import { useMemo, useRef, useEffect } from "react";
import type { SkillModel } from "./skill-model";
import { buildSceneAdapter, activeObjectsForState, layoutForState } from "./scene-adapter";

function renderObjectGraphic(shape: string, fill: string, assetUrl?: string) {
  switch (shape) {
    case "simready-mesh":
      return (
        <div className="simready-asset-graphic" aria-hidden="true">
          <img
            src={assetUrl || "/assets/simready/engineComponent_engine_mount_a01.png"}
            alt=""
            width="56"
            height="56"
            className="simready-thumb-img"
            style={{ objectFit: "contain", borderRadius: "4px" }}
          />
        </div>
      );
    case "lego-cockpit":
      return (
        <svg viewBox="0 0 80 80" width="56" height="56" className="lego-svg" aria-hidden="true">
          <circle cx="40" cy="40" r="36" fill={fill} stroke="#1b2126" strokeWidth="3" />
          <circle cx="40" cy="40" r="26" fill="#1b2126" stroke="#4a5664" strokeWidth="2" />
          <circle cx="40" cy="40" r="14" fill="#303b45" />
          <circle cx="40" cy="40" r="5" fill="#111" />
          <line x1="40" y1="14" x2="40" y2="66" stroke="#4a5664" strokeWidth="1.5" />
          <line x1="14" y1="40" x2="66" y2="40" stroke="#4a5664" strokeWidth="1.5" />
        </svg>
      );
    case "lego-wing":
      return (
        <svg viewBox="0 0 70 90" width="52" height="68" className="lego-svg" aria-hidden="true">
          <polygon points="35,4 66,22 66,68 35,86 4,68 4,22" fill={fill} stroke="#353e48" strokeWidth="2.5" />
          <line x1="35" y1="12" x2="35" y2="78" stroke="#3d4752" strokeWidth="2" />
          <line x1="14" y1="28" x2="56" y2="62" stroke="#2b323a" strokeWidth="1.5" />
          <line x1="14" y1="62" x2="56" y2="28" stroke="#2b323a" strokeWidth="1.5" />
          <circle cx="35" cy="45" r="9" fill="#4d5866" stroke="#222" strokeWidth="1.5" />
        </svg>
      );
    case "lego-strut":
      return (
        <svg viewBox="0 0 48 36" width="40" height="30" className="lego-svg" aria-hidden="true">
          <rect x="6" y="10" width="36" height="16" rx="3" fill={fill} stroke="#2a323a" strokeWidth="2" />
          <rect x="18" y="4" width="12" height="6" rx="2" fill="#8895a5" stroke="#2a323a" strokeWidth="1" />
          <line x1="14" y1="14" x2="34" y2="14" stroke="#4c5663" strokeWidth="1" />
        </svg>
      );
    case "lego-stud":
      return (
        <svg viewBox="0 0 28 28" width="22" height="22" className="lego-svg" aria-hidden="true">
          <circle cx="14" cy="14" r="11" fill={fill} stroke="#2e3740" strokeWidth="1.5" />
          <circle cx="14" cy="14" r="5" fill="#b0bccb" stroke="#4a5563" strokeWidth="1" />
        </svg>
      );
    case "lego-plate":
      return (
        <svg viewBox="0 0 80 28" width="66" height="22" className="lego-svg" aria-hidden="true">
          <rect x="12" y="3" width="12" height="5" rx="1.5" fill="#758291" />
          <rect x="34" y="3" width="12" height="5" rx="1.5" fill="#758291" />
          <rect x="56" y="3" width="12" height="5" rx="1.5" fill="#758291" />
          <rect x="4" y="8" width="72" height="15" rx="2" fill={fill} stroke="#2b333c" strokeWidth="1.5" />
        </svg>
      );
    default:
      return <span className="object-shape" aria-hidden="true" />;
  }
}

/**
 * Visual procedural scene — renders object visuals positioned according
 * to the scene adapter's layout for the current state.
 *
 * This is presentation with disclosed provenance, not a physics simulation
 * or a claim about learned geometry. Procedural logic remains strictly in the
 * shared Skill Model.
 */
export function ProcedureScene({
  model,
  state,
  activeActionId,
  reducedMotion = false,
}: {
  model: SkillModel;
  state: string[];
  activeActionId?: string;
  reducedMotion?: boolean;
}) {
  const adapter = useMemo(() => buildSceneAdapter(model), [model]);
  const prevStateRef = useRef(state);

  useEffect(() => {
    prevStateRef.current = state;
  }, [state]);

  const activeIds = activeObjectsForState(adapter, state);
  const layout = layoutForState(adapter, state);
  const stateLabels = state
    .map((id) => model.states?.find((s) => s.id === id)?.label ?? id.replaceAll("_", " "))
    .filter(Boolean);

  const activeAction = activeActionId
    ? model.actions.find((a) => a.id === activeActionId)
    : undefined;

  return (
    <div
      className={`procedure-scene layout-${layout} provenance-${adapter.provenance}`}
      aria-label="Visual procedural state"
      role="img"
    >
      <div className="scene-provenance">
        <small>
          {adapter.provenance === "simready-asset-nvidia"
            ? `NVIDIA SimReady Asset: ${adapter.assetReference ?? "engineComponent_engine_mount_a01"} · License: ${adapter.licenseNotice ?? "CC-BY-4.0"} · Visual presentation only · Procedural rules come from Skill Model`
            : adapter.provenance === "hand-authored-fixture"
              ? "Illustrative layout — hand-authored for this fixture"
              : adapter.provenance === "task-specific-mapping"
                ? "Task-specific visual arrangement for LEGO assembly · Manually authored geometry, not learned physics · Procedural rules come from Skill Model"
                : "Placeholder layout — no task-specific geometry"}
        </small>
      </div>

      <div className="scene-objects">
        {[...adapter.objects.values()].map((visual) => {
          const isActive = activeIds.includes(visual.id);
          const isInAction = activeAction?.objectIds.includes(visual.id) ?? false;
          const objName = model.objects.find((o) => o.id === visual.id)?.name ?? visual.id;

          return (
            <div
              key={visual.id}
              className={[
                "scene-object",
                `shape-${visual.shape}`,
                isActive ? "active" : "inactive",
                isInAction ? "in-action" : "",
                reducedMotion ? "reduced-motion" : "",
              ].join(" ")}
              style={{
                "--obj-fill": visual.fill,
                "--obj-w": visual.width,
                "--obj-h": visual.height,
              } as React.CSSProperties}
              aria-label={`${objName}${isActive ? " (active)" : " (not yet used)"}`}
            >
              <span className="object-label">{objName}</span>
              {renderObjectGraphic(visual.shape, visual.fill, visual.assetUrl)}
            </div>
          );
        })}
      </div>

      {stateLabels.length > 0 && (
        <div className="scene-state-labels" aria-live="polite">
          {stateLabels.map((label) => (
            <span className="scene-state-chip" key={label}>{label}</span>
          ))}
        </div>
      )}

      {activeAction && (
        <div className="scene-active-action">
          <span className="eyebrow">CURRENT STEP</span>
          <strong>{activeAction.label}</strong>
        </div>
      )}

      {adapter.unmappedObjectIds.length > 0 && (
        <small className="scene-unmapped">
          {adapter.unmappedObjectIds.length} object{adapter.unmappedObjectIds.length === 1 ? "" : "s"} without visual mapping — shown as neutral placeholders.
        </small>
      )}
    </div>
  );
}
