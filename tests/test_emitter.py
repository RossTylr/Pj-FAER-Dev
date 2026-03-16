"""Tests for emitter.py (EX-3 extraction).

Validates TypedEmitter produces populated frozen SimEvent dataclasses
and satisfies the EventEmitter Protocol. Closes K-7.

Run: pytest tests/test_emitter.py -v
"""
import pytest


class TestEmitterProtocol:
    """Verify Protocol conformance and module purity."""

    def test_no_simpy_import(self):
        pytest.skip("Implement after NB36")

    def test_typed_emitter_satisfies_protocol(self):
        """TypedEmitter must satisfy EventEmitter Protocol (runtime_checkable)."""
        pytest.skip("Implement after NB36")


class TestK7Closure:
    """Verify typed event fields are populated (K-7)."""

    def test_triage_event_has_detail(self):
        """TRIAGED event detail field must not be empty."""
        pytest.skip("Implement after NB36")

    def test_all_event_types_populated(self):
        """Every event type published by TypedEmitter must have non-empty fields."""
        pytest.skip("Implement after NB36")


class TestDispositionInvariant:
    """KL-6: DISPOSITION count == ARRIVAL count."""

    def test_nb32_disposition_equals_arrival(self, nb32_config):
        pytest.skip("Implement after NB36 and engine wiring")
