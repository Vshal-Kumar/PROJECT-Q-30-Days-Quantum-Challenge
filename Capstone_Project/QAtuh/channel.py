import random
from qiskit import QuantumCircuit, ClassicalRegister

class QuantumChannel:
    """
    Simulates a quantum channel connecting Alice and Bob.
    Supports physical depolarizing noise and active intercept-resend (eavesdropping) attacks.
    """
    def __init__(self, noise_rate: float = 0.0, attack_type: str = None):
        """
        Args:
            noise_rate (float): Probability (0.0 to 1.0) of a depolarizing error occurring on the qubit.
            attack_type (str): Type of channel attack. Supported: None, 'eavesdrop'.
        """
        self.noise_rate = noise_rate
        self.attack_type = attack_type
        # Keep track of Eve's basis choices (0 for Z, 1 for X)
        self.eve_bases = []

    def reset(self):
        """Resets simulation telemetry data."""
        self.eve_bases = []

    def transmit(self, circuit: QuantumCircuit, qubit_index: int, eve_creg: ClassicalRegister = None, eve_cbit_index: int = None) -> None:
        """
        Transmits a qubit through the noisy, potentially compromised channel.
        Modifies the Qiskit QuantumCircuit in place.
        """
        # 1. Simulate Quantum Channel Noise (Depolarizing Model)
        if self.noise_rate > 0.0:
            if random.random() < self.noise_rate:
                # Single-qubit depolarizing channel: apply X, Y, or Z with equal probability
                error = random.choice(['X', 'Y', 'Z'])
                if error == 'X':
                    circuit.x(qubit_index)
                elif error == 'Y':
                    circuit.y(qubit_index)
                elif error == 'Z':
                    circuit.z(qubit_index)

        # 2. Simulate Eavesdropping Attack (Intercept-Resend)
        if self.attack_type == 'eavesdrop':
            # Eve chooses a random measurement basis: 0 for Z, 1 for X
            eve_basis = random.choice([0, 1])
            self.eve_bases.append(eve_basis)

            # If X basis, transform to diagonal basis
            if eve_basis == 1:
                circuit.h(qubit_index)

            # Perform intercept measurement
            if eve_creg is not None and eve_cbit_index is not None:
                circuit.measure(qubit_index, eve_creg[eve_cbit_index])

            # If X basis, transform back (resend)
            if eve_basis == 1:
                circuit.h(qubit_index)
