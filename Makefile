# Veil developer targets. Run from the repo root.
UV = uv run --project veil

.PHONY: test gate eval

test:
	$(UV) pytest veil/tests -q

# Preregistered gate (gate/GATE.md). Needs gate/labels/*.json, gate/clips/*.mp4 and runs/<clip_id>/ for each clip:
#   $(UV) veil run gate/clips/c1.mp4 --run-id c1 --stages keyframes,discover,track,extend,listen,redact,audit,report
gate:
	$(UV) python -m gate.score_gate

# Dev set (synthetic fixture, runs/synth) and held-out set (gate clips c1..cN, runs/<clip_id>), reported separately.
eval:
	$(UV) python -m eval.run_eval dev runs/synth eval/results/final
	$(UV) python -m eval.run_eval heldout gate/labels eval/results/final
