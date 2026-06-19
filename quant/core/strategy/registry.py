from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import inspect
import json
from typing import Any

from quant.core.models import StrategyRegistration
from quant.core.strategy.base import Strategy


def build_strategy_registration(
    strategy: Strategy,
    description: str,
    factor_set_id: str,
    research_report_path: str = "",
    status: str = "research",
) -> StrategyRegistration:
    source = _strategy_source(strategy)
    code_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    manifest = build_strategy_manifest(
        strategy=strategy,
        factor_set_id=factor_set_id,
        code_hash=code_hash,
    )
    config_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
    return StrategyRegistration(
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        description=description,
        factor_set_id=factor_set_id,
        code_hash=code_hash,
        config_hash=config_hash,
        config_json=config_json,
        research_report_path=research_report_path,
        status=status,
    )


def build_strategy_manifest(
    *,
    strategy: Strategy,
    factor_set_id: str,
    code_hash: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy.strategy_id,
        "strategy_version": strategy.strategy_version,
        "class_path": _class_path(strategy),
        "factor_set_id": factor_set_id,
        "required_factors": [factor.name for factor in strategy.required_factors()],
        "parameters": _normalize_value(strategy),
        "code_hash": code_hash,
    }


def _strategy_source(strategy: Strategy) -> str:
    sources = [_source_for(strategy)]
    if hasattr(strategy, "base_strategy"):
        base_strategy = getattr(strategy, "base_strategy")
        if isinstance(base_strategy, Strategy):
            sources.append(_strategy_source(base_strategy))
    return "\n".join(sources)


def _source_for(strategy: Strategy) -> str:
    try:
        return inspect.getsource(strategy.__class__)
    except OSError:
        return repr(strategy)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(value[key]) for key in sorted(value)}
    if is_dataclass(value):
        return {
            "class_path": _class_path(value),
            "fields": {
                field.name: _normalize_value(getattr(value, field.name))
                for field in fields(value)
            },
        }
    return repr(value)


def _class_path(value: Any) -> str:
    cls = value.__class__
    return f"{cls.__module__}.{cls.__qualname__}"
