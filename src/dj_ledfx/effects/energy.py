"""BPM-to-energy inference for automatic effect adaptation.

Energy scales amounts (how strong, how many, which power-of-two split of the beat), never a
speed: the tempo sets the pace already, and a speed that changes with the BPM jumps wherever
the phase it scales wraps round.
"""

from __future__ import annotations


def bpm_energy(bpm: float, low: float = 100.0, high: float = 150.0) -> float:
    """Map BPM to 0.0-1.0 energy level. Linear between low and high, clamped."""
    if bpm <= low:
        return 0.0
    if bpm >= high:
        return 1.0
    return (bpm - low) / (high - low)
