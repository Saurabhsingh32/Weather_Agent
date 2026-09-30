"""Resolve a Cursor SDK model selection that works on Start / fixed-settings plans."""

from __future__ import annotations

import os
from typing import Any

from cursor_sdk import Cursor, ModelParameterValue, ModelSelection


def resolve_model(
    api_key: str,
    preferred: str | None = None,
) -> str | ModelSelection:
    """Pick a model the account can actually run.

    On Start, bare ``composer-2.5`` is often rejected unless the catalog
    default variant params (e.g. fast=true) are included. Prefer:

    1. ``CURSOR_MODEL`` env if set (supports ``id`` or ``id:param=value,...``)
    2. Preferred id with its default catalog variant
    3. First catalog model with its default variant
    4. ``auto``
    """
    preferred = (preferred or os.environ.get("CURSOR_MODEL") or "composer-2.5").strip()
    if preferred in {"auto", "default"}:
        return preferred

    if ":" in preferred and "=" in preferred:
        # e.g. composer-2.5:fast=true
        model_id, raw_params = preferred.split(":", 1)
        params = []
        for part in raw_params.split(","):
            if "=" not in part:
                continue
            pid, pval = part.split("=", 1)
            params.append(ModelParameterValue(id=pid.strip(), value=pval.strip()))
        return ModelSelection(id=model_id.strip(), params=tuple(params))

    try:
        catalog = Cursor.models.list(api_key=api_key)
    except Exception:
        return preferred

    by_id = {m.id: m for m in catalog}
    candidate = by_id.get(preferred) or (catalog[0] if catalog else None)
    if candidate is None:
        return "auto"

    for variant in candidate.variants:
        if variant.is_default:
            return ModelSelection(id=candidate.id, params=tuple(variant.params))
    if candidate.variants:
        variant = candidate.variants[0]
        return ModelSelection(id=candidate.id, params=tuple(variant.params))
    return ModelSelection(id=candidate.id)


def model_label(model: str | ModelSelection | Any) -> str:
    if isinstance(model, str):
        return model
    if isinstance(model, ModelSelection):
        params = ",".join(f"{p.id}={p.value}" for p in model.params)
        return f"{model.id}:{params}" if params else model.id
    return str(model)
