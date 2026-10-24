"""Local Gemma readiness checks shared by the macOS setup command and UI."""
from __future__ import annotations

from dataclasses import dataclass

from .model import GemmaLocalClient, LocalModelError


@dataclass(frozen=True)
class ModelReadiness:
    ready: bool
    selected_model: str
    message: str


def evaluate_loaded_models(model_ids: list[str], configured_model: str = "") -> ModelReadiness:
    """Select one loaded Gemma model without exposing prompt or completion data."""
    unique = list(dict.fromkeys(model_ids))
    if not unique:
        return ModelReadiness(False, "", "No model is loaded in LM Studio.")
    if configured_model:
        if configured_model not in unique:
            return ModelReadiness(False, "", "PII_MODEL_ID does not match a loaded LM Studio model.")
        selected = configured_model
    elif len(unique) == 1:
        selected = unique[0]
    else:
        return ModelReadiness(False, "", "Multiple models are loaded; set PII_MODEL_ID to the intended Gemma model.")
    if "gemma" not in selected.casefold():
        return ModelReadiness(False, selected, "The selected fallback model is not identified as Gemma.")
    return ModelReadiness(True, selected, "A loaded Gemma fallback is available on loopback.")


def probe_local_gemma(client: GemmaLocalClient) -> ModelReadiness:
    try:
        return evaluate_loaded_models(client.list_models(), client.model_id)
    except LocalModelError:
        return ModelReadiness(False, "", "LM Studio is not reachable on the configured loopback endpoint.")
