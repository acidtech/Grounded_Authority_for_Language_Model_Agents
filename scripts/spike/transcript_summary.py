"""CHR gate spike: transcript summary (throwaway tooling). Never stores line text.

One implementation for the whole kit:
- probe_hook.py imports summarize() and records one summary per transcript path
  named in a hook payload, taken at hook time.
- Both runners call the CLI after their runs:
      python3 transcript_summary.py OUT_DIR
  It reads OUT_DIR/hooks.jsonl, summarizes every distinct transcript path named
  in a payload (transcript_path, agent_transcript_path) and writes
  OUT_DIR/transcripts-summary.jsonl (one line per path, with the run labels that
  named it).

A summary holds path, exists, size, line_count and marker hits for DELEG-123,
CITE-NONCE-7 and SPIKE-CTX-n. A hit is the 1-based line number plus the line's
structural kind (the JSONL record's type/role labels, for example
"assistant/assistant" or "response_item/message/assistant"), so it shows WHO
wrote the marker without copying any text.
"""

import json
import os
import re
import sys

TRANSCRIPT_KEYS = ("transcript_path", "agent_transcript_path")
MARKERS = ("DELEG-123", "CITE-NONCE-7")
SPIKE_CTX = re.compile(r"SPIKE-CTX-(\d+)")
_KIND_LABEL = re.compile(r"[A-Za-z_]{1,40}")


def _line_kind(line: str) -> str | None:
    """Structural kind of a JSONL transcript line (type/role labels only), never its text."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    labels = []
    for holder in (obj, obj.get("payload"), obj.get("message")):
        if isinstance(holder, dict):
            for key in ("type", "role"):
                value = holder.get(key)
                if isinstance(value, str) and _KIND_LABEL.fullmatch(value):
                    labels.append(value)
    return "/".join(labels) or None


def summarize(path: str) -> dict:
    summary: dict = {"path": path, "exists": os.path.isfile(path)}
    if not summary["exists"]:
        return summary
    markers: dict = {marker: [] for marker in MARKERS}
    spike_ctx: dict = {}
    line_count = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, 1):
            line_count = number
            found = [marker for marker in MARKERS if marker in line]
            ctx_numbers = sorted(set(SPIKE_CTX.findall(line)), key=int)
            if not found and not ctx_numbers:
                continue
            hit = {"line": number, "kind": _line_kind(line)}
            for marker in found:
                markers[marker].append(hit)
            for n in ctx_numbers:
                spike_ctx.setdefault(n, []).append(hit)
    summary["size"] = os.path.getsize(path)
    summary["line_count"] = line_count
    summary["markers"] = markers
    summary["spike_ctx"] = {n: spike_ctx[n] for n in sorted(spike_ctx, key=int)}
    return summary


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: transcript_summary.py OUT_DIR", file=sys.stderr)
        return 2
    out_dir = argv[1]
    hooks = os.path.join(out_dir, "hooks.jsonl")
    if not os.path.isfile(hooks):
        print(f"transcript_summary: no {hooks}: no hook fired; check the stderr files", file=sys.stderr)
        return 1
    labels: dict[str, list] = {}
    with open(hooks, encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            payload = record["payload"]
            if not isinstance(payload, dict):
                continue
            for key in TRANSCRIPT_KEYS:
                path = payload.get(key)
                if isinstance(path, str):
                    seen = labels.setdefault(path, [])
                    if record["label"] not in seen:
                        seen.append(record["label"])
    dest = os.path.join(out_dir, "transcripts-summary.jsonl")
    with open(dest, "w", encoding="utf-8") as fh:
        for path, path_labels in labels.items():
            fh.write(json.dumps({"labels": path_labels, **summarize(path)}) + "\n")
    print(f"summarized {len(labels)} transcript(s) to {dest} (no transcript text stored)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
