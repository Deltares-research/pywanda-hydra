"""Unit tests for postprocessing.extraction.extractors registry helpers."""

from __future__ import annotations

import unittest
from unittest import mock

from pydantic import BaseModel

from pywandahydra.postprocessing.extraction import extractors


class _ParamsA(BaseModel):
    threshold: float = 1.0


class _ExtractorA:
    name = "extractor_a"
    description = "Extractor A"
    Params = _ParamsA

    def __init__(self, params: _ParamsA | None = None) -> None:
        self._p = params or self.Params()

    def extract(self, ctx: object) -> dict:
        del ctx
        return {}


class _ExtractorADuplicate:
    name = "extractor_a"
    description = "Duplicate"
    Params = _ParamsA

    def __init__(self, params: _ParamsA | None = None) -> None:
        self._p = params or self.Params()

    def extract(self, ctx: object) -> dict:
        del ctx
        return {}


class TestRegisterExtractor(unittest.TestCase):
    def setUp(self) -> None:
        extractors._EXTRACTOR_CLASSES.pop("extractor_a", None)
        self.addCleanup(extractors._EXTRACTOR_CLASSES.pop, "extractor_a", None)  # type: ignore[call-arg]

    def test_register_returns_existing_on_duplicate(self) -> None:
        first = extractors.register_extractor(_ExtractorA)
        second = extractors.register_extractor(_ExtractorADuplicate)

        self.assertIs(first, _ExtractorA)
        self.assertIs(second, _ExtractorA)
        self.assertIs(extractors.get_extractor_class("extractor_a"), _ExtractorA)


class TestGetExtractorClass(unittest.TestCase):
    def test_unknown_extractor_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            extractors.get_extractor_class("does_not_exist")


class TestResolveExtractor(unittest.TestCase):
    def setUp(self) -> None:
        extractors._EXTRACTOR_CLASSES.pop("extractor_a", None)
        extractors.register_extractor(_ExtractorA)
        self.addCleanup(extractors._EXTRACTOR_CLASSES.pop, "extractor_a", None)  # type: ignore[call-arg]

    def test_resolve_with_default_params(self) -> None:
        instance = extractors.resolve_extractor("extractor_a")

        self.assertIsInstance(instance, _ExtractorA)
        self.assertEqual(instance._p.threshold, 1.0)  # type: ignore[attr-defined]

    def test_resolve_with_custom_params(self) -> None:
        instance = extractors.resolve_extractor("extractor_a", {"threshold": 5.0})

        self.assertEqual(instance._p.threshold, 5.0)  # type: ignore[attr-defined]

    def test_resolve_unknown_extractor_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            extractors.resolve_extractor("does_not_exist")


class TestBootstrap(unittest.TestCase):
    def test_bootstrap_registers_entry_points(self) -> None:
        extractors._EXTRACTOR_CLASSES.pop("extractor_a", None)
        self.addCleanup(extractors._EXTRACTOR_CLASSES.pop, "extractor_a", None)  # type: ignore[call-arg]

        fake_ep = mock.Mock()
        fake_ep.name = "extractor_a"
        fake_ep.value = "some.module:ExtractorA"
        fake_ep.load.return_value = _ExtractorA

        fake_eps = mock.Mock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch.object(extractors, "entry_points", return_value=fake_eps):
            extractors.bootstrap()

        self.assertIs(extractors.get_extractor_class("extractor_a"), _ExtractorA)

    def test_bootstrap_logs_warning_on_load_failure(self) -> None:
        fake_ep = mock.Mock()
        fake_ep.name = "broken"
        fake_ep.value = "broken.module:Broken"
        fake_ep.load.side_effect = ImportError("nope")

        fake_eps = mock.Mock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch.object(extractors, "entry_points", return_value=fake_eps):
            # Should not raise despite the entry point failing to load.
            extractors.bootstrap()

    def test_bootstrap_python39_get_fallback(self) -> None:
        extractors._EXTRACTOR_CLASSES.pop("extractor_a", None)
        self.addCleanup(extractors._EXTRACTOR_CLASSES.pop, "extractor_a", None)  # type: ignore[call-arg]

        fake_ep = mock.Mock()
        fake_ep.name = "extractor_a"
        fake_ep.value = "some.module:ExtractorA"
        fake_ep.load.return_value = _ExtractorA

        # An object lacking 'select' so the 3.9 fallback path (eps.get) is used.
        fake_eps = mock.Mock(spec=["get"])
        fake_eps.get.return_value = [fake_ep]

        with mock.patch.object(extractors, "entry_points", return_value=fake_eps):
            extractors.bootstrap()

        self.assertIs(extractors.get_extractor_class("extractor_a"), _ExtractorA)


if __name__ == "__main__":
    unittest.main()
