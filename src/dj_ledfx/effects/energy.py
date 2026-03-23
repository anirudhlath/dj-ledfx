"""BPM-to-energy inference for automatic effect adaptation."""

from __future__ import annotations


def bpm_energy(bpm: float, low: float = 100.0, high: float = 150.0) -> float:
    """Map BPM to 0.0-1.0 energy level. Linear between low and high, clamped."""
    if bpm <= low:
        return 0.0
    if bpm >= high:
        return 1.0
    return (bpm - low) / (high - low)
