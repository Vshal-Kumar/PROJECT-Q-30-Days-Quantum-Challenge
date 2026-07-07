import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

def create_bell(state_type='phi_plus'):
    """
    Creates a Bell state quantum circuit based on the requested type.
    Options: 'phi_plus', 'phi_minus', 'psi_plus', 'psi_minus'
    """
    qc = QuantumCircuit(2, 2)
    
    if state_type == 'phi_plus':
        qc.h(0)
        qc.cx(0, 1)
    elif state_type == 'phi_minus':
        qc.x(0)
        qc.h(0)
        qc.cx(0, 1)
    elif state_type == 'psi_plus':
        qc.h(0)
        qc.cx(0, 1)
        qc.x(1)
    elif state_type == 'psi_minus':
        qc.x(0)
        qc.h(0)
        qc.cx(0, 1)
        qc.x(1)
        
    qc.measure([0, 1], [0, 1])
    return qc

def run_circuit(qc, shots=1024):
    """
    Runs the quantum circuit on the Aer Simulator and returns counts.
    """
    simulator = AerSimulator()
    result = simulator.run(qc, shots=shots).result()
    return result.get_counts()

def get_circuit_image_b64(qc):
    """
    Draws the quantum circuit using matplotlib and returns a base64 encoded PNG string.
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