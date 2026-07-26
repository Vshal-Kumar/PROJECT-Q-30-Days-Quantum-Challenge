import os
import random
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit_aer import AerSimulator
from .crypto import derive_bases

class EPRAuthenticator:
    """
    Implements a statistical, EPR-based challenge-response quantum identity authentication protocol.
    Instead of single-shot verification, it uses a batch of entangled pairs and checks correlation
    statistics against a threshold to tolerate channel noise and detect attackers.
    """
    def __init__(self, secret: bytes, batch_size: int = 100, threshold: float = 0.15):
        """
        Args:
            secret (bytes): The server's pre-shared secret key.
            batch_size (int): The number of EPR pairs used per authentication session.
            threshold (float): The maximum allowed QBER (Quantum Bit Error Rate) to accept authentication.
        """
        self.secret = secret
        self.batch_size = batch_size
        self.threshold = threshold
        self.simulator = AerSimulator()

    def run_authentication(self, alice_secret: bytes, channel, impersonate: bool = False, replay_data: list[int] = None) -> dict:
        """
        Runs the authentication handshake simulation.
        
        Args:
            alice_secret (bytes): The secret key Alice uses (may mismatch Bob's if unauthorized).
            channel (QuantumChannel): The quantum communication channel.
            impersonate (bool): True if Eve is attempting to impersonate Alice without the secret.
            replay_data (list[int]): If provided, simulates a replay attack where Eve sends recorded responses.

        Returns:
            dict: Simulation results including authentication success, QBER, results, and circuit metadata.
        """
        # 1. Bob generates a random challenge salt
        challenge = os.urandom(16)

        # 2. Derive measurement bases
        # Bob derives bases using his registered secret
        bob_bases = derive_bases(self.secret, challenge, self.batch_size)

        # Alice (or the entity claiming to be Alice) derives bases
        if impersonate:
            # Eve doesn't know the secret, so she must choose random bases
            alice_bases = [random.choice([0, 1]) for _ in range(self.batch_size)]
        else:
            # Alice uses her secret to derive bases
            alice_bases = derive_bases(alice_secret, challenge, self.batch_size)

        # 3. Create Quantum Registers
        # Bob has N qubits (0 to N-1), Alice has N qubits (N to 2N-1)
        qr = QuantumRegister(2 * self.batch_size, name='q')
        bob_creg = ClassicalRegister(self.batch_size, name='bob')
        alice_creg = ClassicalRegister(self.batch_size, name='alice')
        
        circuit = QuantumCircuit(qr, bob_creg, alice_creg)

        # Add Eve's classical register if there is an active eavesdropper on the channel
        eve_creg = None
        if channel.attack_type == 'eavesdrop':
            eve_creg = ClassicalRegister(self.batch_size, name='eve')
            circuit.add_register(eve_creg)

        # 4. Bob prepares EPR Pairs (Bell state |Phi+>)
        for i in range(self.batch_size):
            circuit.h(qr[i])
            circuit.cx(qr[i], qr[self.batch_size + i])

        # 5. Transmit Alice's qubits (N to 2N-1) through the Quantum Channel
        for i in range(self.batch_size):
            channel.transmit(circuit, qubit_index=self.batch_size + i, eve_creg=eve_creg, eve_cbit_index=i)

        # 6. Bob measures his qubits in the derived bases
        for i in range(self.batch_size):
            if bob_bases[i] == 1:  # 1 represents X basis
                circuit.h(qr[i])
            circuit.measure(qr[i], bob_creg[i])

        # 7. Alice (or Eve) measures the received qubits in their bases
        for i in range(self.batch_size):
            if alice_bases[i] == 1:  # 1 represents X basis
                circuit.h(qr[self.batch_size + i])
            circuit.measure(qr[self.batch_size + i], alice_creg[i])

        # 8. Simulate the circuit
        # We run 1 shot to simulate a single real-time execution of the handshake
        job = self.simulator.run(circuit, shots=1)
        result = job.result()
        counts = result.get_counts()
        
        # Parse output bits from counts (format is space-separated registers in reverse order)
        raw_bits = list(counts.keys())[0]
        parts = raw_bits.split()
        
        # Order of registers in parts: [eve, alice, bob] or [alice, bob]
        bob_str = parts[-1]
        alice_str = parts[-2]

        # Convert bitstrings back to list of integers in qubit order (0 to N-1)
        # Note: Qiskit returns strings in right-to-left bit order (bit 0 is rightmost)
        bob_results = [int(b) for b in reversed(bob_str)]
        alice_results = [int(b) for b in reversed(alice_str)]

        # 9. Handle Replay Attack Simulation
        # If Eve is replaying old data, she overwrites Alice's measurement results
        if replay_data is not None:
            # Pad or truncate replay data to match batch size
            if len(replay_data) < self.batch_size:
                alice_results = replay_data + [random.choice([0, 1]) for _ in range(self.batch_size - len(replay_data))]
            else:
                alice_results = replay_data[:self.batch_size]

        # 10. Calculate Quantum Bit Error Rate (QBER)
        mismatches = sum(1 for b, a in zip(bob_results, alice_results) if b != a)
        qber = mismatches / self.batch_size

        # 11. Statistical Decision Rule
        authenticated = qber < self.threshold

        # Extract gate counts and depth
        ops = circuit.count_ops()
        gate_count = sum(ops.values()) - ops.get('measure', 0)
        depth = circuit.depth()

        return {
            'authenticated': authenticated,
            'qber': qber,
            'alice_results': alice_results,
            'bob_results': bob_results,
            'circuit': circuit,
            'gate_count': gate_count,
            'depth': depth,
            'challenge': challenge
        }
