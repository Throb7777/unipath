from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


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


def list_client_modes() -> List[dict]:
    return [asdict(mode) for mode in MODE_REGISTRY]
