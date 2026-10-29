"""Gate timing policy: config.json in the state root (C32 Appendix A).

The state root is outside the project tree and read-only to the governed
agent's mutate sandbox, so only the principal sets the policy. Keys:
max_intervening_turns (int >= 0, default 3), the completed nonconsequential
worker turns a gate may survive after its opening, and gate_lifetime_seconds
(int > 0, default 900). An absent file means the defaults. An unknown key, a
wrong type or an out-of-range value raises ConfigError; it never falls back to
a default.
"""

from dataclasses import dataclass
from typing import Any

from chrgate.core.store import Store

CONFIG = "config.json"


class ConfigError(ValueError):
    """config.json in the state root is invalid."""


@dataclass(frozen=True)
class Config:
    max_intervening_turns: int = 3
    gate_lifetime_seconds: int = 900


# key -> smallest allowed value
_MINIMUM = {"max_intervening_turns": 0, "gate_lifetime_seconds": 1}


def load_config(store: Store) -> Config:
    """The gate timing policy; the caller holds store.lock()."""
    raw: Any = store.read(CONFIG, {})
    if not isinstance(raw, dict):
        raise ConfigError(f"{store.root / CONFIG}: expected a JSON object, got {type(raw).__name__}")
    unknown = sorted(set(raw) - set(_MINIMUM))
    if unknown:
        raise ConfigError(f"{store.root / CONFIG}: unknown key(s) {unknown}")
    for key, value in raw.items():
        if type(value) is not int:
            raise ConfigError(f"{store.root / CONFIG}: {key} must be an integer, got {value!r}")
        if value < _MINIMUM[key]:
            raise ConfigError(f"{store.root / CONFIG}: {key} must be >= {_MINIMUM[key]}, got {value}")
    return Config(**raw)
