import random
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit_aer import AerSimulator
from .crypto import derive_aes_key

class BB84KeyExchange:
    """
    Implements the BB84 quantum key distribution protocol.
    Used post-authentication to establish a shared symmetric session key.
    Includes basis sifting, QBER estimation on a test subset, and key derivation.
    """
    def __init__(self, num_qubits: int = 100, threshold: float = 0.11):
        """
        Args:
            num_qubits (int): The number of qubits sent in the BB84 protocol.
            threshold (float): The maximum allowed QBER during parameter estimation before aborting.
        """
        self.num_qubits = num_qubits
        self.threshold = threshold
        self.simulator = AerSimulator()

    def run_key_exchange(self, channel) -> dict:
        """
        Simulates the BB84 key exchange over a quantum channel.

        Args:
            channel (QuantumChannel): The quantum channel connecting Alice and Bob.

        Returns:
            dict: Metrics, sifting data, error rates, and the derived key (if successful).
        """
        # 1. Alice generates random bits and bases (0 for Z, 1 for X)
        alice_bits = [random.choice([0, 1]) for _ in range(self.num_qubits)]
        alice_bases = [random.choice([0, 1]) for _ in range(self.num_qubits)]

        # 2. Bob generates random bases (0 for Z, 1 for X)
        bob_bases = [random.choice([0, 1]) for _ in range(self.num_qubits)]

        # 3. Create Quantum Registers
        qr = QuantumRegister(self.num_qubits, name='q')
        bob_creg = ClassicalRegister(self.num_qubits, name='bob')
        
        circuit = QuantumCircuit(qr, bob_creg)
        
        eve_creg = None
        if channel.attack_type == 'eavesdrop':
            eve_creg = ClassicalRegister(self.num_qubits, name='eve')
            circuit.add_register(eve_creg)

        # 4. Alice prepares qubits in state according to her bits and bases
        for i in range(self.num_qubits):
            if alice_bits[i] == 1:
                circuit.x(qr[i])
            if alice_bases[i] == 1:
                circuit.h(qr[i])

        # 5. Transmit qubits through the Quantum Channel
        for i in range(self.num_qubits):
            channel.transmit(circuit, qubit_index=i, eve_creg=eve_creg, eve_cbit_index=i)

        # 6. Bob measures the received qubits in his bases
        for i in range(self.num_qubits):
            if bob_bases[i] == 1:
                circuit.h(qr[i])
            circuit.measure(qr[i], bob_creg[i])

        # 7. Execute the simulation (1 shot)
        job = self.simulator.run(circuit, shots=1)
        result = job.result()
        counts = result.get_counts()

        raw_bits = list(counts.keys())[0]
        parts = raw_bits.split()

        # Parse Bob's measurement results
        bob_str = parts[-1]
        bob_bits = [int(b) for b in reversed(bob_str)]

        # 8. Sifting Phase
        # Identify indices where Alice and Bob chose matching bases
        matching_indices = [i for i in range(self.num_qubits) if alice_bases[i] == bob_bases[i]]
        
        if not matching_indices:
            return {
                'success': False,
                'reason': 'No matching bases found during sifting',
                'alice_bits_sent': self.num_qubits,
                'sifted_length': 0
            }

        alice_sifted = [alice_bits[i] for i in matching_indices]
        bob_sifted = [bob_bits[i] for i in matching_indices]
        sifted_length = len(matching_indices)

        # 9. Parameter Estimation Phase
        # Use a subset of the sifted key bits to estimate QBER
        # We check 20% of the sifted bits (capped between 5 and 25)
        num_check_bits = max(5, min(25, sifted_length // 5))
        
        # Shuffle matching indices and split into check and key indices
        check_indices = random.sample(range(sifted_length), num_check_bits)
        check_indices.sort(reverse=True) # Sort in reverse to delete without offset issues

        check_alice = []
        check_bob = []
        
        # Copy the test bits
        for idx in check_indices:
            check_alice.append(alice_sifted[idx])
            check_bob.append(bob_sifted[idx])

        # Calculate error rate on the test subset
        errors = sum(1 for a, b in zip(check_alice, check_bob) if a != b)
        qber = errors / num_check_bits if num_check_bits > 0 else 0.0

        # Remove check bits from the key pool
        for idx in check_indices:
            alice_sifted.pop(idx)
            bob_sifted.pop(idx)

        # 10. Key Extraction & Abort check
        success = qber <= self.threshold
        reason = ""
        derived_key = None

        if success:
            if len(alice_sifted) > 0:
                derived_key = derive_aes_key(alice_sifted)
                reason = "Key established successfully"
            else:
                success = False
                reason = "No sifted bits left after error checking"
        else:
            reason = f"QBER ({qber:.2%}) exceeds security threshold ({self.threshold:.2%})"

        # Extract gate counts and depth
        ops = circuit.count_ops()
        gate_count = sum(ops.values()) - ops.get('measure', 0)
        depth = circuit.depth()

        return {
            'success': success,
            'reason': reason,
            'qber': qber,
            'sifted_length': sifted_length,
            'check_bits_used': num_check_bits,
            'key_bits_remaining': len(alice_sifted),
            'derived_key': derived_key,
            'gate_count': gate_count,
            'depth': depth
        }
