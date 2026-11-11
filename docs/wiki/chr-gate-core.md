# chr-gate core library

> `chrgate.core` is the gate itself: work orders, witnesses, the action gate, claims, citations, delegation and testimony, kept as locked JSON state outside the project tree.

## Key Files
- [gate.py](../../chr-gate/src/chrgate/core/gate.py): `open_gate`, `take_gate`, `note_turn`, `close_gate`, `new_epoch`
- [workorder.py](../../chr-gate/src/chrgate/core/workorder.py): proposals, `activate`, `revoke`, the frame registry, `resolve`
- [witness.py](../../chr-gate/src/chrgate/core/witness.py): `WitnessIssuer`, the only witness issuer
- [claims.py](../../chr-gate/src/chrgate/core/claims.py): the first-argument claim check and `authorize`
- [citations.py](../../chr-gate/src/chrgate/core/citations.py) and [nonces.py](../../chr-gate/src/chrgate/core/nonces.py): `<cite>` tags and `ctx:` context nonces
- [delegation.py](../../chr-gate/src/chrgate/core/delegation.py): child work orders and inherited bounds
- [testimony.py](../../chr-gate/src/chrgate/core/testimony.py): append-only `testimony.jsonl`
- [store.py](../../chr-gate/src/chrgate/core/store.py), [paths.py](../../chr-gate/src/chrgate/core/paths.py), [config.py](../../chr-gate/src/chrgate/core/config.py), [events.py](../../chr-gate/src/chrgate/core/events.py): the lock and atomic JSON writes, the state root, the timing policy, `events.jsonl`

## How It Works
State lives in `${XDG_STATE_HOME:-~/.local/state}/chr-gate/<project key>/`, the key being 16 hex of the sha256 of the project realpath (`CHR_GATE_PROJECT`, else the working directory). Every operation runs inside `Store.lock()` and checks before it writes, so a refusal changes no state.

The agent proposes text (`P-xxxxxxxx`); only the user's prompt activates it as `wo:ID.vN`, and activation or revocation clears the witness and gate of the frames it governs. `read_work_order` returns the text and the frame's `wit:` witness, the same one for each binding (work order id, version, frame, epoch). Disk holds only its sha256, and a read cancels a pending gate.

`open_gate` returns "read your work order" on any mismatch, else the full text. `take_gate` is the check for each consequential call: the gate is current, younger than `gate_lifetime_seconds` (default 900), within `max_intervening_turns` research turns (default 3) and not in the opening turn. The first call consumes the gate for its turn key, so the parallel calls of one batch share it. `new_epoch` (compaction) ends witness and gate. Claims are checked for presence and a `wo:ID.vN` citation, never truth. A delegated order (`DW-...`) lives only while its parent version is current.

## Try it
Run `scripts/unit_suite.sh` from the repository root. Install with `uv tool install --editable /path/to/repo/chr-gate`, follow "A first session" in the [chr-gate README](../../chr-gate/README.md), and watch `events.jsonl` in the state root log each decision.

## Cross-References
- [chr-gate hooks](chr-gate-hooks.md) and [chr-gate server](chr-gate-server.md)

## Gotchas
- `Store.lock()` is not reentrant; a function whose caller must hold it raises `LockNotHeld` outside it.
- A bad `config.json` raises `ConfigError`; it never falls back to defaults.
- A server restart issues a new witness. Expiry and consumption end the gate, never the witness.
- chr-gate refuses to govern its own source tree.
