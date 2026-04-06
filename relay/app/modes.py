from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class ModeDefinition:
    id: str
    label: str
    description: str
    category: str
    outputKind: str
    requiresNormalizedUrl: bool = True
    requiresArticleBodyFetch: bool = False
    supportsBrowserPrefetch: bool = False
    preferredExecutors: tuple[str, ...] = ()
    enabled: bool = True
    isCustom: bool = False


MODE_REGISTRY: List[ModeDefinition] = [
    ModeDefinition(
        id="paper_harvest_v1",
        label="Strict Paper Harvest",
        description="Only keep explicitly mentioned papers and fail if the article body cannot be fetched.",
        category="paper_harvest",
        outputKind="paper_list",
        requiresArticleBodyFetch=True,
        supportsBrowserPrefetch=True,
        preferredExecutors=("openclaw",),
    ),
    ModeDefinition(
        id="paper_harvest_relaxed_v1",
        label="Relaxed Paper Harvest",
        description="Use a looser parsing strategy for unstable pages.",
        category="paper_harvest",
        outputKind="paper_list",
        requiresArticleBodyFetch=True,
        supportsBrowserPrefetch=True,
        preferredExecutors=("openclaw",),
    ),
    ModeDefinition(
        id="link_only_v1",
        label="Forward Link Only",
        description="Only forward the normalized link downstream without paper extraction.",
        category="link_forward",
        outputKind="link_summary",
        preferredExecutors=("openclaw", "shell_command", "mock"),
    ),
]

MODE_BY_ID: Dict[str, ModeDefinition] = {mode.id: mode for mode in MODE_REGISTRY}


def _custom_mode_to_definition(custom_mode: Any) -> ModeDefinition:
    return ModeDefinition(
        id=custom_mode.id,
        label=custom_mode.label,
        description=custom_mode.description or "User-defined shell command mode.",
        category="custom",
        outputKind="custom_result",
        preferredExecutors=(custom_mode.executor_kind,),
        enabled=bool(getattr(custom_mode, "enabled", True)),
        isCustom=True,
    )


def custom_mode_ids_for_executor(custom_modes: Iterable[Any], executor_kind: str) -> tuple[str, ...]:
    return tuple(
        mode.id
        for mode in custom_modes
        if getattr(mode, "enabled", True) and getattr(mode, "executor_kind", "") == executor_kind
    )


def mode_registry(custom_modes: Iterable[Any] = ()) -> List[ModeDefinition]:
    registry = list(MODE_REGISTRY)
    registry.extend(_custom_mode_to_definition(mode) for mode in custom_modes if getattr(mode, "enabled", True))
    return registry


def mode_map(custom_modes: Iterable[Any] = ()) -> Dict[str, ModeDefinition]:
    return {mode.id: mode for mode in mode_registry(custom_modes)}


def list_client_modes(custom_modes: Iterable[Any] = ()) -> List[dict]:
    return [asdict(mode) for mode in mode_registry(custom_modes)]
