"""Open-vocabulary discovery: Muse Spark proposes what in a frame could identify the creator."""
import base64
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from pydantic import Field, ValidationError
from rapidfuzz import fuzz

from veil.schemas import Candidate, Concept, DiscoverArtifact, DiscoverError, Keyframe, Strict

PROMPT_VERSION = 'discover_v1'
PROMPT_PATH = Path(__file__).resolve().parents[1] / 'prompts' / 'discover_v1.txt'
BASELINE = ['face', 'license plate', 'phone screen', 'paper document']
MERGE_RATIO = 85
MAX_IN_FLIGHT = 4
REPAIR_NOTE = 'Return only valid JSON matching the schema.'


class Item(Strict):
    concept: str = Field(min_length=1)
    sam_prompt: str = Field(min_length=1)
    why_identifying: str
    confidence: float = Field(ge=0, le=1)


class Items(Strict):
    items: list[Item] = Field(max_length=8)


Ask = Callable[[Path, str | None], tuple[str, str]]  # (frame path, repair note) -> (raw text, model id)


def parse_items(text: str) -> list[Item]:
    return Items.model_validate_json(text.strip()).items


def discover_frame(ask: Ask, path: Path) -> tuple[list[Item], str, str | None]:
    """One call, one repair retry on invalid JSON. Returns (items, model_id, error)."""
    text, model_id = ask(path, None)
    try:
        return parse_items(text), model_id, None
    except (ValidationError, ValueError):
        pass
    text, model_id = ask(path, REPAIR_NOTE)
    try:
        return parse_items(text), model_id, None
    except (ValidationError, ValueError) as exc:
        return [], model_id, f'invalid JSON after repair retry: {type(exc).__name__}'


def normalize(phrase: str) -> str:
    words = re.findall(r'[a-z0-9]+', phrase.lower())
    words = [w for w in words if w not in ('a', 'an', 'the')]
    words = [w[:-1] if len(w) > 3 and w.endswith('s') and not w.endswith('ss') else w for w in words]
    return ' '.join(words)


def build_concepts(candidates: list[Candidate]) -> list[Concept]:
    """Merge spark candidates whose normalized sam_prompt has rapidfuzz ratio >= 85; baseline is kept apart."""
    groups: list[list[Candidate]] = []
    for c in sorted((c for c in candidates if c.source == 'spark'), key=lambda c: (-c.confidence, c.frame_idx)):
        for g in groups:
            if fuzz.ratio(normalize(g[0].sam_prompt), normalize(c.sam_prompt)) >= MERGE_RATIO:
                g.append(c)
                break
        else:
            groups.append([c])
    concepts = []
    for g in groups:
        slug = re.sub(r'\W+', '-', normalize(g[0].sam_prompt)).strip('-')
        concepts.append(Concept(concept_id=f'spark-{slug}', sam_prompt=g[0].sam_prompt, source='spark',
                                first_frame_idx=min(c.frame_idx for c in g), candidate_ids=[c.candidate_id for c in g],
                                max_confidence=max(c.confidence for c in g), why_identifying=g[0].why_identifying))
    for name in BASELINE:
        concepts.append(Concept(concept_id='baseline-' + name.replace(' ', '-'), sam_prompt=name, source='baseline',
                                first_frame_idx=0, candidate_ids=[], max_confidence=1.0,
                                why_identifying='fixed baseline class'))
    return concepts


def run(keyframes: list[Keyframe], frames_dir: Path, ask: Ask) -> DiscoverArtifact:
    def one(kf: Keyframe):
        try:
            return kf, discover_frame(ask, frames_dir / kf.path)
        except Exception as exc:  # transport/API failure: recorded, never turned into candidates
            return kf, ([], '', f'call failed: {type(exc).__name__}: {str(exc)[:200]}')

    with ThreadPoolExecutor(MAX_IN_FLIGHT) as pool:
        results = list(pool.map(one, keyframes))
    candidates, errors, model_id = [], [], ''
    for kf, (items, mid, err) in results:
        model_id = mid or model_id
        if err:
            errors.append(DiscoverError(frame_idx=kf.frame_idx, error=err))
        for n, it in enumerate(items):
            candidates.append(Candidate(candidate_id=f'f{kf.frame_idx}-{n}', concept=it.concept,
                                        sam_prompt=it.sam_prompt, frame_idx=kf.frame_idx,
                                        why_identifying=it.why_identifying, confidence=it.confidence,
                                        source='spark', model_id=mid))
    return DiscoverArtifact(prompt_version=PROMPT_VERSION, model_id=model_id, candidates=candidates,
                            concepts=build_concepts(candidates), errors=errors)


def make_spark_ask(client, ledger, root: Path, model: str = 'muse-spark-1.3') -> Ask:
    """Hosted Spark via the Responses API with a strict JSON schema; each call is reserved in the ledger."""
    from veil.providers.common import save
    prompt = PROMPT_PATH.read_text().strip()
    schema = Items.model_json_schema()
    (root / 'discover_raw').mkdir(parents=True, exist_ok=True)

    def ask(path: Path, repair: str | None):
        name = f'discover-{path.stem}' + ('-repair' if repair else '')
        start = ledger.begin(name, model, '/v1/responses', f'1 keyframe JPEG ({path.name})')
        content = [{'type': 'input_text', 'text': prompt + (' ' + repair if repair else '')},
                   {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode()}]
        try:
            resp = client.responses.create(model=model, reasoning={'effort': 'minimal'}, max_output_tokens=2000,
                                           input=[{'role': 'user', 'content': content}],
                                           text={'format': {'type': 'json_schema', 'name': 'discover_items',
                                                            'strict': True, 'schema': schema}})
            usage = resp.usage.model_dump()
            save(root / 'discover_raw' / f'{name}.json', resp.model_dump(mode='json'))
            ledger.finish(name, start, usage=usage,
                          estimated_usd=(usage['input_tokens'] * 1.25 + usage['output_tokens'] * 4.25) / 1e6)
            return resp.output_text, model
        except Exception as exc:
            ledger.fail(name, start, exc)
            raise
    return ask
