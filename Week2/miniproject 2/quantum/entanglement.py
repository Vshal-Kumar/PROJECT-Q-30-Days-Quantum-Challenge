import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

def create_entanglement(alice_basis='Z', bob_basis='Z'):
    """
    Creates an entangled pair and performs measurements in the specified bases.
    Bases can be 'Z' (computational) or 'X' (diagonal).
    """
    qc = QuantumCircuit(2, 2)
    
    # Create Bell State |Phi+>
    qc.h(0)
    qc.cx(0, 1)
    
    qc.barrier()
    
    # Alice's measurement basis transformation
    if alice_basis == 'X':
        qc.h(0)
        
    # Bob's measurement basis transformation
    if bob_basis == 'X':
        qc.h(1)
        
    qc.measure([0, 1], [0, 1])
    return qc

def run_entanglement(qc, shots=1024):
    """
    Runs the entanglement circuit on the Aer Simulator.
    """
    simulator = AerSimulator()
    result = simulator.run(qc, shots=shots).result()
    return result.get_counts()

def get_circuit_image_b64(qc):
    """
    Draws the entanglement circuit using matplotlib and returns a base64 encoded PNG string.
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
