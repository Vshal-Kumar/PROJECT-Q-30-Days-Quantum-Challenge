"""
attack.py
---------
Implements an eavesdropper ("Eve") performing the classic
intercept-resend attack against the BB84 protocol.

Attack procedure, for every qubit traveling from Alice to Bob:
    1. Eve intercepts the qubit before it reaches Bob.
    2. Eve randomly chooses a measurement basis ('Z' or 'X').
    3. Eve measures the qubit in her chosen basis, collapsing it and
       obtaining a classical bit.
    4. Eve re-prepares a fresh qubit encoding the bit she measured, in
       the basis she used to measure it.
    5. Eve forwards the freshly prepared qubit on to Bob.

Because Eve's basis choice is independent of Alice's, roughly half the
time she guesses the wrong basis. When that happens, the qubit she
forwards to Bob is prepared in the wrong basis relative to Alice's
original encoding, introducing errors that are detectable through an
elevated Quantum Bit Error Rate (QBER).
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

from bb84 import (
    BASIS_Z,
    BASIS_X,
    VALID_BASES,
    generate_random_bases,
    measure_qubit,
    encode_qubit,
)


class Eve:
    """Represents an eavesdropper performing an intercept-resend attack."""

    def __init__(self, n_qubits: int, seed: int | None = None):
        self.n_qubits = n_qubits
        self.bases = generate_random_bases(n_qubits, seed=seed)
        self.measured_bits: np.ndarray = np.zeros(n_qubits, dtype=int)

    def intercept_and_resend(
        self, incoming_qubits: list[QuantumCircuit]
    ) -> list[QuantumCircuit]:
        """
        Intercept every qubit in transit, measure it in a randomly
        chosen basis, and prepare + forward a replacement qubit.

        Args:
            incoming_qubits: The qubit circuits as sent by Alice.

        Returns:
            A new list of qubit circuits, re-prepared by Eve, to be
            forwarded on to Bob over the quantum channel.
        """
        if len(incoming_qubits) != self.n_qubits:
            raise ValueError(
                "Number of incoming qubits does not match Eve's configured n_qubits."
            )

        forwarded_qubits: list[QuantumCircuit] = []

        for i, qc in enumerate(incoming_qubits):
            eve_basis = str(self.bases[i])

            # Step 1-3: intercept and measure in Eve's chosen basis.
            measured_bit = measure_qubit(qc, eve_basis)
            self.measured_bits[i] = measured_bit

            # Step 4-5: re-prepare a fresh qubit in the same basis Eve
            # used, encoding the bit she observed, then forward it.
            resent_qubit = encode_qubit(measured_bit, eve_basis)
            forwarded_qubits.append(resent_qubit)

        return forwarded_qubits


def simulate_intercept_resend_attack(
    alice_qubits: list[QuantumCircuit], n_qubits: int, seed: int | None = None
) -> tuple[list[QuantumCircuit], Eve]:
    """
    Convenience function that instantiates an Eve and runs the full
    intercept-resend attack against a list of qubits sent by Alice.

    Args:
        alice_qubits: Qubit circuits produced by Alice.
        n_qubits: Number of qubits (must match len(alice_qubits)).
        seed: Optional RNG seed for reproducibility.

    Returns:
        Tuple of (qubits forwarded to Bob, the Eve instance used, for
        later analysis / visualization of her basis choices and
        measured bits).
    """
    eve = Eve(n_qubits, seed=seed)
    forwarded_qubits = eve.intercept_and_resend(alice_qubits)
    return forwarded_qubits, eve
