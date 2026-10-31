"""Transparent temporal comparison over source-linked creative memories."""

from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256

from .contracts import Evidence, EvolutionFinding, Memory


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"expected an ISO date (YYYY-MM-DD), got {value!r}") from exc


def _evidence(memory: Memory, theme: str) -> Evidence:
    return Evidence(
        memory_id=memory.id,
        source_id=memory.source_id,
        date=memory.date,
        title=memory.title,
        summary=memory.summary,
        theme=theme,
    )


def discover_evolution(
    *, project_id: str, project_title: str, memories: list[Memory],
    extraction_provider: str = "fixture", extraction_model: str | None = None,
) -> EvolutionFinding | None:
    """Find the clearest theme shift between the earlier and later halves.

    A finding requires two distinct source memories for both themes. The split is
    deterministic and deliberately simple for the baseline; later evaluation can
    replace or tune it without changing the result contract.
    """
    ordered = sorted(memories, key=lambda item: (_parse_date(item.date), item.id))
    if len(ordered) < 4:
        return None

    midpoint = len(ordered) // 2
    earlier, later = ordered[:midpoint], ordered[midpoint:]
    earlier_counts = Counter(theme for item in earlier for theme in dict.fromkeys(item.themes))
    later_counts = Counter(theme for item in later for theme in dict.fromkeys(item.themes))

    if not earlier_counts or not later_counts:
        return None

    earlier_rates = {theme: count / len(earlier) for theme, count in earlier_counts.items()}
    later_rates = {theme: count / len(later) for theme, count in later_counts.items()}
    themes = list(dict.fromkeys([*earlier_counts, *later_counts]))
    deltas = {theme: later_rates.get(theme, 0.0) - earlier_rates.get(theme, 0.0) for theme in themes}
    rising = [theme for theme in themes if deltas[theme] > 0]
    falling = [theme for theme in themes if deltas[theme] < 0]
    if not rising or not falling:
        return None

    # Stable list order breaks ties; prevalence avoids selecting a rare theme
    # when a more dominant theme has the same proportional change.
    later_theme = max(rising, key=lambda theme: (deltas[theme], later_rates[theme], later_counts[theme]))
    earlier_theme = max(falling, key=lambda theme: (-deltas[theme], earlier_rates[theme], earlier_counts[theme]))

    earlier_support = [item for item in earlier if earlier_theme in item.themes]
    later_support = [item for item in later if later_theme in item.themes]
    if len({item.source_id for item in earlier_support}) < 2 or len({item.source_id for item in later_support}) < 2:
        return None

    counter_items = [item for item in later if earlier_theme in item.themes]
    evidence = tuple(
        [_evidence(item, earlier_theme) for item in earlier_support]
        + [_evidence(item, later_theme) for item in later_support]
    )
    counter_evidence = tuple(_evidence(item, earlier_theme) for item in counter_items)
    shared_themes = set(earlier_counts) & set(later_counts)
    continuity_evidence = tuple(
        _evidence(
            item,
            max(
                (theme for theme in shared_themes if theme in item.themes),
                key=lambda theme: (earlier_counts[theme] + later_counts[theme], theme),
            ),
        )
        for item in later
        if any(theme in item.themes for theme in shared_themes)
    )
    dates = [_parse_date(item.date) for item in ordered]
    digest = sha256(f"{project_id}:{earlier_theme}:{later_theme}".encode()).hexdigest()[:10]

    uncertainty = [
        "The early/late split is a simple chronological midpoint, not a learned change-point model.",
    ]
    if extraction_provider == "fixture":
        uncertainty.insert(0, "Themes are human-authored annotations in this synthetic fixture.")
    if counter_evidence:
        uncertainty.append("The earlier theme still appears in later work, so this may be an expansion rather than a replacement.")
    if continuity_evidence and not counter_evidence:
        uncertainty.append("Other project themes persist across both periods, so describe this as an evolution of emphasis rather than a complete replacement.")

    return EvolutionFinding(
        id=f"evolution-{digest}",
        project_id=project_id,
        project_title=project_title,
        hypothesis=(
            f"Across this project, emphasis appears to move from '{earlier_theme}' "
            f"toward '{later_theme}' in the dated artifacts."
        ),
        earlier_theme=earlier_theme,
        later_theme=later_theme,
        start_date=dates[0].isoformat(),
        end_date=dates[-1].isoformat(),
        supporting_evidence=evidence,
        counter_evidence=counter_evidence,
        continuity_evidence=continuity_evidence,
        uncertainty=tuple(uncertainty),
        extraction_provider=extraction_provider,
        extraction_model=extraction_model,
    )
