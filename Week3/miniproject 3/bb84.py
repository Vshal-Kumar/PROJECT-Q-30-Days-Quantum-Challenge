"""
bb84.py
-------
Core implementation of the BB84 Quantum Key Distribution protocol.

Implements:
    - Random bit generation
    - Random basis generation
    - Qubit encoding (state preparation)
    - Quantum circuit creation
    - Quantum channel simulation
    - Measurement in a chosen basis
    - Basis reconciliation (sifting)
    - Shared secret key generation

Basis convention:
    'Z'  ->  Computational (rectilinear) basis  {|0>, |1>}
    'X'  ->  Hadamard (diagonal) basis          {|+>, |->}

Bit -> State mapping (before basis transform):
    0 -> |0>
    1 -> |1>
An 'X' basis encoding additionally applies a Hadamard gate, turning
|0> -> |+> and |1> -> |->.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
BASIS_Z = "Z"   # Computational / rectilinear basis
BASIS_X = "X"   # Hadamard / diagonal basis
VALID_BASES = (BASIS_Z, BASIS_X)

_SIMULATOR = AerSimulator()


# ----------------------------------------------------------------------
# Random generation utilities
# ----------------------------------------------------------------------
def generate_random_bits(n: int, seed: int | None = None) -> np.ndarray:
    """
    Generate an array of n uniformly random classical bits (0 or 1).

    Args:
        n: Number of bits to generate.
        seed: Optional RNG seed for reproducibility.

    Returns:
        NumPy array of shape (n,) containing 0/1 integers.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=n)


def generate_random_bases(n: int, seed: int | None = None) -> np.ndarray:
    """
    Generate an array of n randomly chosen measurement/encoding bases.

    Each basis is either 'Z' (computational) or 'X' (Hadamard), chosen
    with equal probability.

    Args:
        n: Number of bases to generate.
        seed: Optional RNG seed for reproducibility.

    Returns:
        NumPy array of shape (n,) containing dtype='<U1' strings ('Z' or 'X').
    """
    rng = np.random.default_rng(seed)
    choices = rng.integers(0, 2, size=n)
    return np.where(choices == 0, BASIS_Z, BASIS_X)


# ----------------------------------------------------------------------
# Qubit encoding / state preparation
# ----------------------------------------------------------------------
def encode_qubit(bit: int, basis: str) -> QuantumCircuit:
    """
    Build a single-qubit circuit that prepares the BB84 state
    corresponding to (bit, basis).

    Args:
        bit: Classical bit value (0 or 1) to encode.
        basis: Encoding basis, 'Z' or 'X'.

    Returns:
        A QuantumCircuit with 1 qubit and 1 classical bit, with the
        appropriate state-preparation gates applied. Measurement is
        NOT included here; it is added later depending on the
        receiver's chosen measurement basis.
    """
    if basis not in VALID_BASES:
        raise ValueError(f"Invalid basis '{basis}'. Must be one of {VALID_BASES}.")
    if bit not in (0, 1):
        raise ValueError(f"Invalid bit '{bit}'. Must be 0 or 1.")

    qc = QuantumCircuit(1, 1, name=f"encode_b{bit}_{basis}")

    # Start from |0>. Apply X to flip to |1> if the bit is 1.
    if bit == 1:
        qc.x(0)

    # Apply Hadamard to rotate into the diagonal (X) basis if required.
    if basis == BASIS_X:
        qc.h(0)

    return qc


def encode_qubits(bits: np.ndarray, bases: np.ndarray) -> list[QuantumCircuit]:
    """
    Encode an entire sequence of classical bits into BB84 quantum states.

    Args:
        bits: Array of classical bits (0/1).
        bases: Array of encoding bases ('Z'/'X'), same length as bits.

    Returns:
        List of single-qubit QuantumCircuits, one per bit.
    """
    if len(bits) != len(bases):
        raise ValueError("bits and bases arrays must be the same length.")
    return [encode_qubit(int(b), str(basis)) for b, basis in zip(bits, bases)]


# ----------------------------------------------------------------------
# Measurement
# ----------------------------------------------------------------------
def measure_qubit(circuit: QuantumCircuit, basis: str, shots: int = 1) -> int:
    """
    Measure a single-qubit circuit in the given basis and return the
    resulting classical bit.

    Measuring in the 'X' basis is implemented by applying a Hadamard
    gate before the standard computational-basis measurement, which
    rotates the |+>/|-> states onto |0>/|1>.

    Args:
        circuit: The QuantumCircuit representing the incoming qubit
            (as produced by encode_qubit, or by an eavesdropper).
        basis: Measurement basis, 'Z' or 'X'.
        shots: Number of simulation shots (default 1, since a real
            qubit collapses to a single outcome per measurement).

    Returns:
        The measured classical bit (0 or 1).
    """
    if basis not in VALID_BASES:
        raise ValueError(f"Invalid basis '{basis}'. Must be one of {VALID_BASES}.")

    qc = circuit.copy()
    if basis == BASIS_X:
        qc.h(0)
    qc.measure(0, 0)

    transpiled = qc
    job = _SIMULATOR.run(transpiled, shots=shots, memory=True)
    result = job.result()
    outcomes = result.get_memory(transpiled)
    # With shots=1 there is exactly one outcome; take the first.
    return int(outcomes[0])


def measure_qubits(circuits: list[QuantumCircuit], bases: np.ndarray) -> np.ndarray:
    """
    Measure a sequence of single-qubit circuits, each in its
    corresponding chosen basis.

    Args:
        circuits: List of QuantumCircuits (one qubit each) to measure.
        bases: Array of measurement bases ('Z'/'X'), same length as circuits.

    Returns:
        NumPy array of measured classical bits.
    """
    if len(circuits) != len(bases):
        raise ValueError("circuits and bases must be the same length.")
    return np.array(
        [measure_qubit(qc, str(basis)) for qc, basis in zip(circuits, bases)]
    )


# ----------------------------------------------------------------------
# Basis reconciliation (sifting) and key generation
# ----------------------------------------------------------------------
def sift_key(
    alice_bases: np.ndarray,
    bob_bases: np.ndarray,
    alice_bits: np.ndarray,
    bob_bits: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Perform basis reconciliation ("sifting"): keep only the bit
    positions where Alice's and Bob's bases agree.

    Args:
        alice_bases: Alice's basis choices.
        bob_bases: Bob's basis choices.
        alice_bits: Alice's original bit values.
        bob_bits: Bob's measured bit values.

    Returns:
        Tuple of (matching_indices, alice_sifted_key, bob_sifted_key).
    """
    matching_indices = np.where(np.array(alice_bases) == np.array(bob_bases))[0]
    alice_sifted_key = np.array(alice_bits)[matching_indices]
    bob_sifted_key = np.array(bob_bits)[matching_indices]
    return matching_indices, alice_sifted_key, bob_sifted_key


# ----------------------------------------------------------------------
# High-level Alice / Bob roles
# ----------------------------------------------------------------------
class Alice:
    """Represents the sender in the BB84 protocol."""

    def __init__(self, n_qubits: int, seed: int | None = None):
        self.n_qubits = n_qubits
        self.bits = generate_random_bits(n_qubits, seed=seed)
        self.bases = generate_random_bases(
            n_qubits, seed=None if seed is None else seed + 1
        )
        self.qubits: list[QuantumCircuit] = encode_qubits(self.bits, self.bases)

    def send_qubits(self) -> list[QuantumCircuit]:
        """Return the prepared quantum states to be sent over the quantum channel."""
        return self.qubits


class Bob:
    """Represents the receiver in the BB84 protocol."""

    def __init__(self, n_qubits: int, seed: int | None = None):
        self.n_qubits = n_qubits
        self.bases = generate_random_bases(n_qubits, seed=seed)
        self.bits: np.ndarray | None = None

    def receive_and_measure(self, incoming_qubits: list[QuantumCircuit]) -> np.ndarray:
        """
        Measure each incoming qubit in Bob's independently chosen basis.

        Args:
            incoming_qubits: The qubits arriving over the quantum channel
                (possibly tampered with by an eavesdropper).

        Returns:
            Bob's array of measured bits.
        """
        self.bits = measure_qubits(incoming_qubits, self.bases)
        return self.bits


class QuantumChannel:
    """
    Simulates the quantum channel connecting Alice and Bob.

    In the absence of an eavesdropper this is a lossless, noiseless
    identity channel: the circuits sent by Alice arrive unmodified at
    Bob. An eavesdropper (see attack.py) can intercept and tamper with
    the qubits as they pass through this channel.
    """

    @staticmethod
    def transmit(qubits: list[QuantumCircuit]) -> list[QuantumCircuit]:
        """Pass qubits through the channel unmodified (copies to avoid aliasing)."""
        return [qc.copy() for qc in qubits]


class ClassicalChannel:
    """
    Simulates the authenticated public classical channel used by Alice
    and Bob to compare bases (and, during error estimation, a random
    sample of key bits). Assumed to be authenticated (Eve cannot forge
    messages on it) but readable by anyone, per the standard BB84
    security model.
    """

    @staticmethod
    def compare_bases(
        alice_bases: np.ndarray, bob_bases: np.ndarray
    ) -> np.ndarray:
        """Publicly compare bases and return the indices that match."""
        return np.where(np.array(alice_bases) == np.array(bob_bases))[0]
