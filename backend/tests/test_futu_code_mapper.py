from __future__ import annotations

import unittest

from backend.futu.code_mapper import futu_to_qlib, qlib_to_futu, validate_futu_code
from backend.futu.exceptions import InvalidSecurityCodeError


class CodeMapperTests(unittest.TestCase):
    def test_bidirectional_mapping(self) -> None:
        self.assertEqual(qlib_to_futu("SH600104"), "SH.600104")
        self.assertEqual(qlib_to_futu("SZ000001"), "SZ.000001")
        self.assertEqual(futu_to_qlib("SH.600104"), "SH600104")
        self.assertEqual(futu_to_qlib("SZ.000001"), "SZ000001")

    def test_illegal_codes_raise(self) -> None:
        for code in ("HK00700", "600104", "SH.60010", "US.AAPL", ""):
            with self.subTest(code=code), self.assertRaises(InvalidSecurityCodeError):
                validate_futu_code(code)


if __name__ == "__main__":
    unittest.main()
