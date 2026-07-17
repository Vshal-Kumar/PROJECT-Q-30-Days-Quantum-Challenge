"""
detect.py
---------
Implements Quantum Bit Error Rate (QBER) calculation and eavesdropping
detection for the BB84 protocol.

After sifting, Alice and Bob publicly reveal a random sample of their
sifted key bits over the classical channel and compare them. Any
disagreement indicates either natural channel noise or the disturbance
introduced by an eavesdropper performing measurements (per the
no-cloning theorem, any measurement by Eve disturbs the quantum
states with non-zero probability).

QBER = (number of mismatched sample bits) / (total compared bits)

A QBER above a chosen security threshold (commonly ~11% for BB84,
the theoretical bound above which no secure key can be distilled)
indicates that an eavesdropper is very likely present, and the key
should be discarded.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Standard BB84 security threshold. Below this, secure key
# distillation (error correction + privacy amplification) is
# theoretically possible. Above it, the channel is considered
# compromised and the key is discarded.
DEFAULT_QBER_THRESHOLD = 0.11


@dataclass
class QBERResult:
    """Container for the outcome of a QBER / eavesdropping analysis."""

    compared_bits: int
    error_count: int
    qber: float
    threshold: float
    eavesdropper_detected: bool
    sample_indices: np.ndarray
    final_key_alice: np.ndarray
    final_key_bob: np.ndarray

    @property
    def status_message(self) -> str:
        """Human-readable summary of the detection outcome."""
        return "Eavesdropper Detected" if self.eavesdropper_detected else "Safe Communication"


def calculate_qber(
    alice_sifted_key: np.ndarray,
    bob_sifted_key: np.ndarray,
    sample_fraction: float = 0.5,
    seed: int | None = None,
) -> tuple[float, int, int, np.ndarray]:
    """
    Randomly sample a fraction of the sifted key and compute the
    Quantum Bit Error Rate between Alice's and Bob's revealed bits.

    Args:
        alice_sifted_key: Alice's sifted key bits.
        bob_sifted_key: Bob's sifted key bits (same length as Alice's).
        sample_fraction: Fraction of the sifted key to publicly reveal
            and compare for error estimation (default 50%).
        seed: Optional RNG seed for reproducible sampling.

    Returns:
        Tuple of (qber, error_count, compared_bits, sample_indices).
    """
    if len(alice_sifted_key) != len(bob_sifted_key):
        raise ValueError("Alice's and Bob's sifted keys must be the same length.")

    n = len(alice_sifted_key)
    if n == 0:
        return 0.0, 0, 0, np.array([], dtype=int)

    sample_size = max(1, int(round(n * sample_fraction)))
    rng = np.random.default_rng(seed)
    sample_indices = rng.choice(n, size=sample_size, replace=False)
    sample_indices.sort()

    alice_sample = alice_sifted_key[sample_indices]
    bob_sample = bob_sifted_key[sample_indices]

    errors = np.sum(alice_sample != bob_sample)
    compared_bits = sample_size
    qber = errors / compared_bits if compared_bits > 0 else 0.0

    return float(qber), int(errors), int(compared_bits), sample_indices


def detect_eavesdropping(qber: float, threshold: float = DEFAULT_QBER_THRESHOLD) -> bool:
    """
    Decide, based on the measured QBER, whether an eavesdropper is
    present on the quantum channel.

    Args:
        qber: The computed Quantum Bit Error Rate.
        threshold: Security threshold above which the channel is
            considered compromised.

    Returns:
        True if an eavesdropper is detected (QBER exceeds threshold),
        False otherwise.
    """
    return qber > threshold


def analyze_key(
    alice_sifted_key: np.ndarray,
    bob_sifted_key: np.ndarray,
    sample_fraction: float = 0.5,
    threshold: float = DEFAULT_QBER_THRESHOLD,
    seed: int | None = None,
) -> QBERResult:
    """
    Full end-to-end analysis: estimate QBER from a public sample,
    detect eavesdropping, and derive the final secret key from the
    remaining (unrevealed) sifted bits.

    Args:
        alice_sifted_key: Alice's sifted key bits.
        bob_sifted_key: Bob's sifted key bits.
        sample_fraction: Fraction of sifted bits to sacrifice for
            error estimation.
        threshold: QBER security threshold.
        seed: Optional RNG seed for reproducible sampling.

    Returns:
        A populated QBERResult describing the outcome.
    """
    qber, errors, compared, sample_indices = calculate_qber(
        alice_sifted_key, bob_sifted_key, sample_fraction, seed
    )
    eavesdropper_detected = detect_eavesdropping(qber, threshold)

    # The final key is composed of the sifted bits that were NOT
    # revealed during public error estimation.
    all_indices = np.arange(len(alice_sifted_key))
    remaining_mask = np.ones(len(alice_sifted_key), dtype=bool)
    remaining_mask[sample_indices] = False
    remaining_indices = all_indices[remaining_mask]

    if eavesdropper_detected:
        # Discard the key entirely if eavesdropping is detected.
        final_key_alice = np.array([], dtype=int)
        final_key_bob = np.array([], dtype=int)
    else:
        final_key_alice = alice_sifted_key[remaining_indices]
        final_key_bob = bob_sifted_key[remaining_indices]

    return QBERResult(
        compared_bits=compared,
        error_count=errors,
        qber=qber,
        threshold=threshold,
        eavesdropper_detected=eavesdropper_detected,
        sample_indices=sample_indices,
        final_key_alice=final_key_alice,
        final_key_bob=final_key_bob,
    )


def print_detection_report(result: QBERResult) -> None:
    """Pretty-print a QBERResult to the console."""
    print("=" * 60)
    print("EAVESDROPPING DETECTION REPORT")
    print("=" * 60)
    print(f"Compared bits (public sample) : {result.compared_bits}")
    print(f"Mismatched bits (errors)      : {result.error_count}")
    print(f"Quantum Bit Error Rate (QBER)  : {result.qber:.4f} ({result.qber * 100:.2f}%)")
    print(f"Security threshold             : {result.threshold:.4f} ({result.threshold * 100:.2f}%)")
    print("-" * 60)
    print(f"STATUS: {result.status_message}")
    print("=" * 60)
    if not result.eavesdropper_detected:
        print(f"Final shared secret key length : {len(result.final_key_alice)} bits")
