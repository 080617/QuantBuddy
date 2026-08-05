"""Strict conversion between Qlib and Futu A-share security codes."""

from __future__ import annotations

import re

from .exceptions import InvalidSecurityCodeError

_QLIB = re.compile(r"^(SH|SZ)(\d{6})$")
_FUTU = re.compile(r"^(SH|SZ)\.(\d{6})$")


def qlib_to_futu(code: str) -> str:
    match = _QLIB.fullmatch(code.strip().upper()) if isinstance(code, str) else None
    if not match:
        raise InvalidSecurityCodeError(f"Invalid Qlib A-share code: {code!r}")
    return f"{match.group(1)}.{match.group(2)}"


def futu_to_qlib(code: str) -> str:
    match = _FUTU.fullmatch(code.strip().upper()) if isinstance(code, str) else None
    if not match:
        raise InvalidSecurityCodeError(f"Invalid Futu A-share code: {code!r}")
    return f"{match.group(1)}{match.group(2)}"


def validate_futu_code(code: str) -> str:
    normalized = code.strip().upper() if isinstance(code, str) else ""
    if not _FUTU.fullmatch(normalized):
        raise InvalidSecurityCodeError(f"Only SH.xxxxxx or SZ.xxxxxx is accepted: {code!r}")
    return normalized
