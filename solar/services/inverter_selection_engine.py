"""
solar/services/inverter_selection_engine.py

PHASE 5 COMPATIBILITY INTERFACE

All actual inverter engineering and selection logic lives in:

    solar.services.inverter_engine

This module exists only to preserve existing imports and provide
a clean compatibility boundary.
"""

from solar.services.inverter_engine import (
    ENGINE_NAME,
    ENGINE_VERSION,
    calculate_inverter,
    calculate_inverter_requirement,
    evaluate_inverter,
    run_inverter_engine,
    select_best_inverter,
    select_inverter,
)


__all__ = [
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "calculate_inverter",
    "calculate_inverter_requirement",
    "evaluate_inverter",
    "run_inverter_engine",
    "select_best_inverter",
    "select_inverter",
]