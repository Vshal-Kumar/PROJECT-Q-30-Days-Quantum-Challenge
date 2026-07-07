import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

def create_teleportation(theta=0.0):
    """
    Creates a quantum teleportation circuit.
    theta: rotation angle in radians for Alice's input state RY(theta) |0>.
    - theta = 0: |0> state
    - theta = pi: |1> state
    - theta = pi/2: |+> state
    """
    qc = QuantumCircuit(3, 3)
    
    # 1. Prepare Alice's input state on Qubit 0
    qc.ry(theta, 0)
    
    qc.barrier()
    
    # 2. Create EPR pair on Qubits 1 and 2 (Entanglement between Alice and Bob)
    qc.h(1)
    qc.cx(1, 2)
    
    qc.barrier()
    
    # 3. Alice performs Bell measurement operations on Qubits 0 and 1
    qc.cx(0, 1)
    qc.h(0)
    
    qc.barrier()
    
    # 4. Bob applies corrections on Qubit 2 based on Alice's qubits
    qc.cx(1, 2)
    qc.cz(0, 2)
    
    qc.barrier()
    
    # 5. Measure all qubits
    # Classical bit 0 -> Qubit 0 (Alice)
    # Classical bit 1 -> Qubit 1 (Alice)
    # Classical bit 2 -> Qubit 2 (Bob's teleported qubit)
    qc.measure([0, 1, 2], [0, 1, 2])
    
    return qc

def run_teleportation(qc, shots=1024):
    """
    Runs the teleportation circuit on the Aer Simulator.
    """
    simulator = AerSimulator()
    result = simulator.run(qc, shots=shots).result()
    return result.get_counts()

def get_circuit_image_b64(qc):
    """
    Draws the teleportation circuit using matplotlib and returns a base64 encoded PNG string.
    """
    try:
        fig = qc.draw(output='mpl')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_str
    except Exception as e:
        return None