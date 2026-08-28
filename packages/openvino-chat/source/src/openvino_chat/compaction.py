from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_AUTO_COMPACT_RATIO = 0.90
DEFAULT_COMPACT_KEEP_TURNS = 4


@dataclass(frozen=True)
class CompactionResult:
    compacted: bool
    messages_compacted: int = 0
    before_tokens: int = 0
    after_tokens: int = 0
    summary_tokens: int = 0
    reason: str = ""

    @property
    def turns_compacted(self) -> int:
        return self.messages_compacted // 2


def auto_compact_threshold(context_length: int, input_budget: int | None = None) -> int:
    context = max(2, int(context_length))
    threshold = max(1, int(context * DEFAULT_AUTO_COMPACT_RATIO))
    if input_budget is not None:
        threshold = min(threshold, max(1, int(input_budget)))
    return threshold


def compactable_history_end(
    history: list[tuple[str, str]],
    start: int,
    keep_turns: int = DEFAULT_COMPACT_KEEP_TURNS,
) -> int:
    start = max(0, min(int(start), len(history)))
    end = max(start, len(history) - max(1, int(keep_turns)) * 2)
    while end > start and history[end - 1][0] != "assistant":
        end -= 1
    return end


def fallback_compaction_summary(
    previous_summary: str,
    messages: list[tuple[str, str]],
) -> str:
    lines = []
    if previous_summary.strip():
        lines.extend(["Prior compacted memory:", previous_summary.strip(), ""])
    lines.append("Conversation facts:")
    for role, content in messages:
        clean = " ".join(str(content).split())
        if len(clean) > 600:
            clean = clean[:300].rstrip() + " ... " + clean[-300:].lstrip()
        lines.append(f"- {role}: {clean}")
    return "\n".join(lines).strip()


def is_context_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return bool(
        re.search(
            r"context(?: window| length)?(?: limit)?[^.\n]{0,80}"
            r"(?:exceed|overflow|full|too (?:large|long)|maximum)|"
            r"exceed(?:ed|ing)?[^.\n]{0,60}(?:context|ctx)|"
            r"prompt uses \d+ tokens[^.\n]{0,60}(?:context|ctx)|"
            r"max(?:imum)? sequence(?: length)?[^.\n]{0,40}(?:exceed|limit)|"
            r"input[^.\n]{0,40}too (?:large|long)|"
            r"kv cache[^.\n]{0,40}(?:full|limit|exceed)",
            text,
        )
    )
