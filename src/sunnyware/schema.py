# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 167: per-tool JSON schema validation.

Validates tool args against the tool's declared `parameters` spec
before execution. Two modes:

  strict  (default): reject unresolvable type mismatches + missing
                     required. Coercion (int->str, str->int) is
                     attempted first; a violation only fires if the
                     value cannot be coerced.
  lenient: pass original value through on coercion failure. Only
           missing required rejects.

Config:
  SUNNYWARE_SCHEMA_ENABLED=1       master switch (default on)
  SUNNYWARE_SCHEMA_STRICT=1        1=strict, 0=lenient (default strict)
  SUNNYWARE_SCHEMA_ALLOW_EXTRA=1   1=warn extras, 0=reject (default warn)

Design:
  - Pure Python (no pydantic dep).
  - Tools with no `parameters` spec bypass validation.
  - Violations are logged to the audit trail as `schema.violation`.
  - Violations do NOT trip the circuit breaker (LLM error, not tool).
"""

import os


def _enabled() -> bool:
    v = (os.getenv("SUNNYWARE_SCHEMA_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _strict() -> bool:
    v = (os.getenv("SUNNYWARE_SCHEMA_STRICT", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _allow_extra() -> bool:
    v = (os.getenv("SUNNYWARE_SCHEMA_ALLOW_EXTRA", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _coerce(value, target_type):
    """Best-effort coercion. Returns (value, ok)."""
    t = (target_type or "").lower()

    if t in ("string", "str"):
        if isinstance(value, str):
            return value, True
        if isinstance(value, (int, float, bool)):
            return str(value), True
        return value, False

    if t in ("integer", "int"):
        if isinstance(value, bool):
            return value, False
        if isinstance(value, int):
            return value, True
        if isinstance(value, float):
            return int(value), True
        if isinstance(value, str):
            try:
                return int(value.strip()), True
            except Exception:
                return value, False
        return value, False

    if t in ("number", "float"):
        if isinstance(value, bool):
            return value, False
        if isinstance(value, (int, float)):
            return float(value), True
        if isinstance(value, str):
            try:
                return float(value.strip()), True
            except Exception:
                return value, False
        return value, False

    if t in ("boolean", "bool"):
        if isinstance(value, bool):
            return value, True
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("true", "1", "yes", "on"):
                return True, True
            if s in ("false", "0", "no", "off"):
                return False, True
            return value, False
        if isinstance(value, int):
            return bool(value), True
        return value, False

    if t in ("array", "list"):
        if isinstance(value, list):
            return value, True
        return value, False

    if t in ("object", "dict"):
        if isinstance(value, dict):
            return value, True
        return value, False

    return value, True  # unknown type -> don't second-guess


def validate(tool_name, parameters_spec, args):
    """Validate args against parameters_spec.

    Returns one of:
        {"ok": True,  "args": cleaned_args, "warnings": [...]}
        {"ok": False, "error": "schema_violation", "detail": str,
         "schema": dict, "errors": [str, ...]}
    """
    if not _enabled():
        return {"ok": True, "args": args or {}, "warnings": []}
    if not parameters_spec:
        return {"ok": True, "args": args or {}, "warnings": []}

    args = args or {}
    if not isinstance(args, dict):
        return {
            "ok": False,
            "error": "schema_violation",
            "detail": "arguments must be an object",
            "schema": parameters_spec,
            "errors": ["args is not a dict"],
        }

    strict = _strict()
    errors = []
    warnings = []
    cleaned = dict(args)
    spec_keys = set(parameters_spec.keys())
    arg_keys = set(args.keys())

    for key, spec in parameters_spec.items():
        if not isinstance(spec, dict):
            continue
        is_required = bool(spec.get("required"))
        if is_required and key not in args:
            errors.append(f"missing required parameter '{key}'")
            continue
        if key in args:
            expected = spec.get("type", "")
            if expected:
                coerced, ok = _coerce(args[key], expected)
                if ok:
                    cleaned[key] = coerced
                elif strict:
                    errors.append(
                        f"'{key}' expected {expected}, "
                        f"got {type(args[key]).__name__}"
                    )

    extras = arg_keys - spec_keys
    if extras:
        for e in sorted(extras):
            msg = f"unexpected parameter '{e}'"
            if _allow_extra():
                warnings.append(msg)
            else:
                errors.append(msg)

    if errors:
        return {
            "ok": False,
            "error": "schema_violation",
            "detail": "; ".join(errors[:5]),
            "schema": parameters_spec,
            "errors": errors,
        }
    return {"ok": True, "args": cleaned, "warnings": warnings}


def enabled() -> bool:
    return _enabled()


def strict() -> bool:
    return _strict()
