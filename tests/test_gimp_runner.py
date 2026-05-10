"""Тесты для модуля gimp.runner — функция safe_decode."""

import logging

import pytest


class TestSafeDecode:
    """Тесты для функции safe_decode модуля gimp.runner."""

    def test_utf8_strict(self):
        """Чистый UTF-8 проходит без искажений."""
        from retouch.gimp.runner import safe_decode
        raw = "GIMP обработка завершена".encode("utf-8")
        assert safe_decode(raw) == "GIMP обработка завершена"

    def test_cp1251_fallback(self):
        """CP1251-строка декодируется через fallback."""
        from retouch.gimp.runner import safe_decode
        raw = "Ошибка обработки".encode("cp1251")
        result = safe_decode(raw)
        assert "Ошибка" in result
        assert "обработки" in result

    def test_replace_fallback_logs_warning(self, caplog):
        """Третий fallback (replace) логирует предупреждение.

        CP1251 — single-byte кодировка (0x00-0xFF → символ), поэтому
        для реальных байтов третий путь недостижим. Тестируем через
        параметр encodings=["utf-8"]: убираем CP1251 fallback → при
        невалидном UTF-8 попадаем в replace-ветку.
        """
        from retouch.gimp.runner import safe_decode
        raw = b"Error: \x80\x81 nonsense"  # \x80\x81 — невалидный UTF-8
        with caplog.at_level(logging.WARNING, logger="retouch.gimp"):
            result = safe_decode(raw, encodings=["utf-8"])
        assert "nonsense" in result
        assert "замен" in caplog.text.lower()

    def test_cp1251_bytes_do_not_trigger_warning(self, caplog):
        """CP1251-декодированные байты НЕ логируют предупреждение."""
        from retouch.gimp.runner import safe_decode
        raw = "Ошибка обработки".encode("cp1251")
        with caplog.at_level(logging.WARNING, logger="retouch.gimp"):
            safe_decode(raw)
        assert "замен" not in caplog.text.lower()

    def test_empty_bytes(self):
        """Пустой ввод → пустая строка."""
        from retouch.gimp.runner import safe_decode
        assert safe_decode(b"") == ""

    def test_pure_ascii(self):
        """Чистый ASCII проходит через UTF-8 strict."""
        from retouch.gimp.runner import safe_decode
        raw = b"GIMP batch processing completed successfully"
        assert safe_decode(raw) == "GIMP batch processing completed successfully"
