"""Internal overlapping-window reconciliation helpers for long neural sentences."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from typing import Any, cast

from . import neural_preprocessing as _prep
from ._joint_confidence import (
    _confidence_result,
    _entry_probability,
    _policy_decision,
    _resolve_confidence_entry,
    _sentence_confidence,
)
from ._joint_types import (
    _TOP_LEMMA_EDIT_STATE,
    NeuralWindowingError,
    SentenceAnalysis,
    _best_non_root_relation,
    _extract_top_k_edits_for_word,
)
from .confidence import TokenConfidence
from .lemmatize import LemmaSource
from .mst import decode_mst
from .udfeats import feats_from_xpos


def window_body_budget(model: Any) -> int:
    """Return the manifest subword budget available to complete input words."""
    manifest = getattr(model, "manifest", None)
    policy = getattr(manifest, "special_token_policy", None)
    if manifest is not None and policy != _prep.SPECIAL_TOKEN_POLICY:
        raise NeuralWindowingError(
            "windowed neural analysis requires the validated two-token policy "
            f"{_prep.SPECIAL_TOKEN_POLICY}"
        )
    budget = int(model.max_subwords) - 2  # <s> and </s> are validated by the manifest.
    if budget < 1:
        raise NeuralWindowingError(
            f"model subword limit {model.max_subwords} cannot hold two special tokens "
            "and a complete input word"
        )
    return budget


def full_word_lengths(model: Any, words: list[str]) -> list[int]:
    """Measure every word with an untruncated clone of the active tokenizer."""
    tok = getattr(model, "_tok", None)
    if tok is None:
        raise NeuralWindowingError("windowed neural analysis has no tokenizer")
    clone: Any = None
    # Tokenizer.from_str is the tokenizers API's independent clone operation.  The
    # fallbacks keep the test/fake backend contract small without mutating the live
    # tokenizer, whose truncation policy is still used by ordinary inference.
    guard = getattr(model, "_session_lock", None) or nullcontext()
    with guard:
        try:
            from tokenizers import Tokenizer

            if hasattr(tok, "to_str"):
                clone = Tokenizer.from_str(tok.to_str())
        except Exception:
            clone = None
        if clone is None and hasattr(tok, "clone"):
            try:
                clone = tok.clone()
            except Exception:
                clone = None
        if clone is None:
            import copy

            try:
                clone = copy.deepcopy(tok)
            except Exception as exc:  # pragma: no cover - defensive fake/runtime guard
                raise NeuralWindowingError(
                    "could not clone the tokenizer for untruncated window measurement"
                ) from exc
    try:
        no_truncation = getattr(clone, "no_truncation")
        no_truncation()
    except (AttributeError, TypeError) as exc:
        raise NeuralWindowingError(
            "tokenizer cannot disable truncation for whole-word window measurement"
        ) from exc
    try:
        enc = clone.encode(words, is_pretokenized=True)
    except TypeError:
        # Small deterministic fakes often omit the keyword while preserving the
        # same pretokenized semantics.
        enc = clone.encode(words)
    word_ids = getattr(enc, "word_ids", None)
    if callable(word_ids):
        word_ids = word_ids()
    if word_ids is None:
        raise NeuralWindowingError("tokenizer did not expose complete word positions")
    lengths = [0] * len(words)
    for wid in word_ids:
        if wid is None:
            continue
        if not isinstance(wid, int) or wid < 0 or wid >= len(words):
            raise NeuralWindowingError("tokenizer returned an invalid whole-word position")
        lengths[wid] += 1
    if any(length < 1 for length in lengths):
        raise NeuralWindowingError(
            "windowed neural analysis cannot preserve a complete word boundary: "
            "the untruncated tokenizer produced no subwords for an input token"
        )
    return lengths


def pack_windows(lengths: list[int], budget: int) -> list[tuple[int, int]]:
    """Pack complete-word windows with a subword-bounded suffix overlap."""
    if any(length > budget for length in lengths):
        raise NeuralWindowingError(
            "windowed neural analysis refused an individual token whose complete "
            f"subword span exceeds the {budget}-subword body budget"
        )
    target = min(64, budget // 4)
    windows: list[tuple[int, int]] = []
    start = 0
    n = len(lengths)
    while start < n:
        used = 0
        end = start
        while end < n and used + lengths[end] <= budget:
            used += lengths[end]
            end += 1
        if end == start:  # guarded above, retained as a clean boundary error
            raise NeuralWindowingError(
                "windowed neural analysis cannot place a complete token in a model window"
            )
        windows.append((start, end))
        if end == n:
            break

        # Prefer the largest complete suffix not exceeding the target body-subword
        # overlap.  If a single token is wider than that target, retain that one whole
        # token anyway: every boundary must overlap at least one token.
        overlap_start = end - 1
        overlap_used = lengths[overlap_start]
        while overlap_start > start:
            candidate = overlap_used + lengths[overlap_start - 1]
            if candidate > target:
                break
            overlap_start -= 1
            overlap_used = candidate
        if overlap_start <= start or overlap_start >= end:
            raise NeuralWindowingError(
                "windowed neural analysis cannot provide a whole-token overlap with "
                "forward progress at a window boundary"
            )
        start = overlap_start
    return windows


def analyze_windowed(
    model: Any,
    forms: list[str],
    lengths: list[int],
    windows: list[tuple[int, int]],
    *,
    calibration: Any = None,
    context: dict[str, Any] | None = None,
) -> SentenceAnalysis:
    """Analyze windows and reconcile owner fields plus one global dependency tree."""
    np = model._np
    # Assign owners before any window encoder pass.  This lets us process each window
    # sequentially and drop its logits immediately, keeping the 4,096-token dense cap
    # honest even for many windows.
    n = len(forms)
    owners: list[int | None] = [None] * n
    owner_scores = [-1] * n
    prefix = [0]
    for length in lengths:
        prefix.append(prefix[-1] + length)
    for wi, (ws, we) in enumerate(windows):
        for token in range(ws, we):
            score = min(prefix[token] - prefix[ws], prefix[we] - prefix[token + 1])
            # Windows were built left-to-right, so retaining an equal score gives the
            # required deterministic earlier-window tie break.
            if score > owner_scores[token]:
                owner_scores[token] = score
                owners[token] = wi
    if any(owner is None for owner in owners):  # pragma: no cover - packer invariant
        raise NeuralWindowingError("windowed analysis could not assign every token an owner")

    upos = ["X"] * n
    xpos = ["---------"] * n
    lemma = list(forms)
    resolved = [False] * n
    lemma_source = [LemmaSource.IDENTITY] * n
    lemma_source_path = ["identity_fallback"] * n
    verified = [False] * n
    upos_prob: list[float | None] = [None] * n
    lemma_prob: list[float | None] = [None] * n
    token_confidences: list[TokenConfidence | None] = [None] * n
    raw_components: list[dict[str, float]] = [{} for _ in range(n)]
    arc = np.full((n, n + 1), -np.inf, dtype=np.float32)
    # Relation IDs are bounded by the validated manifest label map.  A compact int16
    # candidate grid avoids an R x N² float tensor; -1 means no finite relation score.
    relation_count = len(model.inv["deprel"])
    if relation_count > int(np.iinfo(np.int16).max):
        raise NeuralWindowingError(
            "windowed neural analysis cannot compact a relation map larger than int16"
        )
    rel_ids = np.full((n, n + 1), -1, dtype=np.int16)
    window_relation_entry, window_relation_reason, window_relation_resolution = (
        _resolve_confidence_entry(model, context, "relation")
        if context is not None
        else (None, None, None)
    )
    window_relation_temperature: float | None = None
    if (
        window_relation_entry is not None
        and window_relation_entry.calibrator == "temperature"
        and window_relation_entry.temperature is not None
    ):
        window_relation_temperature = window_relation_entry.temperature
    rel_raw_probs = (
        np.full((n, n + 1), np.nan, dtype=np.float32)
        if context is not None
        else None
    )
    rel_cal_probs = (
        np.full((n, n + 1), np.nan, dtype=np.float32)
        if context is not None
        and window_relation_temperature is not None
        else None
    )
    edit_capture = _TOP_LEMMA_EDIT_STATE.get()
    top_edits_per_tok: list[tuple[tuple[str, float], ...]] | None = (
        [() for _ in range(n)] if edit_capture is not None else None
    )

    for wi, (ws, we) in enumerate(windows):
        chunk = forms[ws:we]
        raw = model._run(chunk)
        if raw.get("_kept") != list(range(we - ws)):
            raise NeuralWindowingError(
                "windowed tokenizer failed to return every complete word in a window"
            )
        local = model._decode(chunk, raw, calibration=calibration, context=context)
        if local.analyzed != (True,) * len(chunk):
            raise NeuralWindowingError(
                "windowed neural analysis produced an incomplete window decode"
            )
        local_arc = np.asarray(raw["arc"][0], dtype=np.float32)
        local_rel = np.asarray(raw["rel"][0])
        for local_i, token in enumerate(range(ws, we)):
            if owners[token] != wi:
                continue
            upos[token] = local.upos[local_i]
            xpos[token] = local.xpos[local_i]
            lemma[token] = local.lemma[local_i]
            resolved[token] = local.lemma_resolved[local_i]
            lemma_source[token] = local.lemma_source[local_i]
            if local.lemma_source_path:
                lemma_source_path[token] = local.lemma_source_path[local_i]
            verified[token] = local.lemma_verified[local_i]
            if top_edits_per_tok is not None and edit_capture is not None:
                top_edits_per_tok[token] = _extract_top_k_edits_for_word(
                    forms[token], raw["lemma"][0, local_i], model.trees, np, edit_capture[0]
                )
            if local.upos_prob:
                upos_prob[token] = local.upos_prob[local_i]
            if local.lemma_script_prob:
                lemma_prob[token] = local.lemma_script_prob[local_i]
            if context is not None:
                from . import calibrate

                local_sp = raw["_word_pos"][local_i]
                # Window outputs retain the same local word ordering; raw task values
                # are stored as one scalar per owned token until global MST selection.
                raw_upos = float(
                    calibrate.top1_confidence(
                        raw["upos"][0, local_sp], 1.0, np=np
                    )
                )
                raw_x = [
                    float(
                        calibrate.top1_confidence(
                            raw[f"x{x_index}"][0, local_sp], 1.0, np=np
                        )
                    )
                    for x_index in range(9)
                ]
                raw_components[token].update(
                    {
                        "upos": raw_upos,
                        "xpos": float(np.prod(raw_x, dtype=np.float64)),
                        "lemma": float(
                            calibrate.top1_confidence(raw["lemma"][0, local_i], 1.0, np=np)
                        ),
                    }
                )
                token_confidences[token] = replace(
                    local.token_confidences[local_i], index=token
                )
            for local_head, score in enumerate(local_arc[local_i]):
                global_head = 0 if local_head == 0 else ws + local_head
                if global_head < 0 or global_head > n:
                    continue
                arc[token, global_head] = score
                rel_vector = np.asarray(local_rel[:, local_i, local_head])
                if np.isfinite(rel_vector).any():
                    # Only the word attached to the artificial ROOT (head 0) may be
                    # labelled root, so the label for any other arc is chosen from
                    # the non-root labels. See _best_non_root_relation.
                    chosen_rel = (
                        int(rel_vector.argmax())
                        if global_head == 0
                        else _best_non_root_relation(rel_vector, model.inv["deprel"])
                    )
                    rel_ids[token, global_head] = np.int16(chosen_rel)
                    if context is not None and rel_raw_probs is not None:
                        safe_rel = np.where(np.isfinite(rel_vector), rel_vector, -1.0e30)
                        rel_raw_probs[token, global_head] = float(
                            calibrate.temperature_softmax(safe_rel, 1.0, np=np)[chosen_rel]
                        )
                        if rel_cal_probs is not None and window_relation_temperature is not None:
                            rel_cal_probs[token, global_head] = float(
                                calibrate.temperature_softmax(
                                    safe_rel, window_relation_temperature, np=np
                                )[chosen_rel]
                            )
        # Explicitly release the large per-window arrays before the next encoder pass.
        del raw, local, local_arc, local_rel

    if not np.isfinite(arc).any(axis=1).all():
        raise NeuralWindowingError(
            "windowed neural analysis did not observe at least one finite arc for "
            "every dependent"
        )
    try:
        heads = decode_mst(arc)
    except Exception as exc:  # pragma: no cover - defensive decoder guard
        raise NeuralWindowingError("global windowed dependency decoding failed") from exc
    if len(heads) != n or heads.count(0) != 1:
        raise NeuralWindowingError(
            "global windowed dependency decoding did not produce exactly one root"
        )
    for dep, head_value in enumerate(heads):
        if head_value < 0 or head_value > n or head_value == dep + 1:
            raise NeuralWindowingError("global windowed decoder selected an invalid arc")
        if not np.isfinite(arc[dep, head_value]):
            raise NeuralWindowingError(
                "global windowed decoder selected an unobserved or non-finite arc"
            )
    # The MST decoder promises an arborescence; retain a cheap explicit cycle check as
    # a safety assertion because malformed all--inf candidate matrices must never leak.
    for start in range(n):
        seen: set[int] = set()
        node = start + 1
        while node:
            if node in seen:
                raise NeuralWindowingError("global windowed dependency tree contains a cycle")
            seen.add(node)
            node = heads[node - 1]

    deprel: list[str] = ["dep"] * n
    for dep, head_value in enumerate(heads):
        if head_value == 0:
            deprel[dep] = "root"
            continue
        relation_id = int(rel_ids[dep, head_value])
        if relation_id < 0:
            raise NeuralWindowingError(
                "global windowed decoder selected an arc without an observed relation"
            )
        deprel[dep] = model.inv["deprel"][relation_id]
    if context is not None:
        from . import calibrate

        for dep, head_value in enumerate(heads):
            arc_row = arc[dep]
            safe_arc = np.where(np.isfinite(arc_row), arc_row, -1.0e30)
            raw_head = float(
                calibrate.temperature_softmax(safe_arc, 1.0, np=np)[head_value]
            )
            raw_components[dep]["head"] = raw_head
            if head_value == 0:
                raw_components[dep]["forced_root"] = 1.0
            else:
                if rel_raw_probs is None:
                    raise NeuralWindowingError(
                        "windowed confidence relation grid was not allocated"
                    )
                raw_components[dep]["relation"] = float(rel_raw_probs[dep, head_value])
            existing = token_confidences[dep]
            if existing is None:
                continue
            head_entry, head_reason, head_resolution = _resolve_confidence_entry(model, context, "head")
            head_value_cal = _entry_probability(
                head_entry, safe_arc, raw_head, np=np, selected_index=head_value
            )
            head_result = _confidence_result(
                model, context, "head", head_value_cal,
                entry=head_entry, reason=head_reason, resolution=head_resolution,
            )
            if head_value == 0:
                relation_result = _confidence_result(
                    model, context, "relation", None, reason="forced_root"
                )
            else:
                relation_entry = window_relation_entry
                relation_reason = window_relation_reason
                relation_resolution = window_relation_resolution
                relation_value = (
                    float(rel_cal_probs[dep, head_value])
                    if rel_cal_probs is not None
                    else _entry_probability(
                        relation_entry,
                        raw_probability=raw_components[dep]["relation"],
                        np=np,
                    )
                )
                relation_result = _confidence_result(
                    model,
                    context,
                    "relation",
                    relation_value,
                    entry=relation_entry,
                    reason=relation_reason,
                    resolution=relation_resolution,
                )
            updated_results = (
                existing.upos,
                existing.xpos,
                existing.feats,
                existing.lemma,
                head_result,
                relation_result,
            )
            decisions = tuple(
                decision
                for result in updated_results
                if (decision := _policy_decision(context.get("policy"), result)) is not None
            )
            token_confidences[dep] = replace(
                existing,
                index=dep,
                head=head_result,
                relation=relation_result,
                policy=decisions,
            )
        if any(item is None for item in token_confidences):
            raise NeuralWindowingError(
                "windowed confidence decode did not produce every owner token"
            )
        token_confidences_final = tuple(
            cast(TokenConfidence, item) for item in token_confidences
        )
        sentence_confidence = _sentence_confidence(model, context, raw_components)
    else:
        token_confidences_final = ()
        sentence_confidence = None
    warning = (
        "windowed neural analysis: complete-word overlapping windows; token tags, "
        "lemmas, and confidence use the farthest-boundary owner (earlier on ties), "
        "and dependencies use one global observed-arc MST",
    )
    if edit_capture is not None and top_edits_per_tok is not None:
        edit_capture[1].append(tuple(top_edits_per_tok))
    return SentenceAnalysis(
        tokens=tuple(forms),
        upos=tuple(upos),
        xpos=tuple(xpos),
        feats=tuple(feats_from_xpos(x) for x in xpos),
        head=tuple(heads),
        deprel=tuple(deprel),
        lemma=tuple(lemma),
        lemma_resolved=tuple(resolved),
        upos_prob=tuple(upos_prob) if calibration is not None or context is not None else (),
        lemma_script_prob=tuple(lemma_prob) if calibration is not None or context is not None else (),
        lemma_source=tuple(lemma_source),
        lemma_source_path=tuple(lemma_source_path) if context is not None else (),
        lemma_verified=tuple(verified),
        analyzed=(True,) * n,
        complete=True,
        truncated=False,
        warnings=warning,
        token_confidences=token_confidences_final,
        sentence_confidence=sentence_confidence,
        receipt=model._receipt(
            input_tokens=n,
            analyzed_tokens=n,
            truncated=False,
            windowed=True,
            context=context,
        ),
    )
