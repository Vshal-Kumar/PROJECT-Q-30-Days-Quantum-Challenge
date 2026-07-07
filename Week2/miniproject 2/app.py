import math
from flask import Flask, render_template, jsonify, request

# Import quantum backend functions
from quantum.bell_states import create_bell, run_circuit, get_circuit_image_b64 as get_bell_circuit_b64
from quantum.entanglement import create_entanglement, run_entanglement, get_circuit_image_b64 as get_entanglement_circuit_b64
from quantum.teleportation import create_teleportation, run_teleportation, get_circuit_image_b64 as get_teleportation_circuit_b64

app = Flask(__name__)

@app.route("/")
def home():
    """Renders the main dashboard page."""
    return render_template("index.html")

@app.route("/api/simulate/bell", methods=["GET"])
def simulate_bell():
    """
    Simulates the Bell state creation.
    Params:
      state_type: 'phi_plus', 'phi_minus', 'psi_plus', 'psi_minus'
      shots: number of simulation runs (default: 1024)
    """
    state_type = request.args.get("state_type", "phi_plus")
    try:
        shots = int(request.args.get("shots", 1024))
    except ValueError:
        shots = 1024

    # Validate state type
    valid_states = ["phi_plus", "phi_minus", "psi_plus", "psi_minus"]
    if state_type not in valid_states:
        state_type = "phi_plus"

    qc = create_bell(state_type)
    counts = run_circuit(qc, shots=shots)
    circuit_b64 = get_bell_circuit_b64(qc)

    # Clean counts: Qiskit returns keys like '00', '11'
    # Ensure they are sorted and padded
    formatted_counts = {k: v for k, v in sorted(counts.items())}

    state_labels = {
        "phi_plus": {"name": "Bell State |Φ⁺⟩", "formula": "|Φ⁺⟩ = (|00⟩ + |11⟩)/√2"},
        "phi_minus": {"name": "Bell State |Φ⁻⟩", "formula": "|Φ⁻⟩ = (|00⟩ - |11⟩)/√2"},
        "psi_plus": {"name": "Bell State |Ψ⁺⟩", "formula": "|Ψ⁺⟩ = (|01⟩ + |10⟩)/√2"},
        "psi_minus": {"name": "Bell State |Ψ⁻⟩", "formula": "|Ψ⁻⟩ = (|01⟩ - |10⟩)/√2"},
    }

    return jsonify({
        "status": "success",
        "counts": formatted_counts,
        "circuit_b64": circuit_b64,
        "state_name": state_labels[state_type]["name"],
        "state_formula": state_labels[state_type]["formula"]
    })

@app.route("/api/simulate/entanglement", methods=["GET"])
def simulate_entanglement():
    """
    Simulates quantum entanglement with custom measurement bases.
    Params:
      alice_basis: 'Z' or 'X'
      bob_basis: 'Z' or 'X'
      shots: number of simulation runs (default: 1024)
    """
    alice_basis = request.args.get("alice_basis", "Z").upper()
    bob_basis = request.args.get("bob_basis", "Z").upper()
    try:
        shots = int(request.args.get("shots", 1024))
    except ValueError:
        shots = 1024

    if alice_basis not in ["Z", "X"]:
        alice_basis = "Z"
    if bob_basis not in ["Z", "X"]:
        bob_basis = "Z"

    qc = create_entanglement(alice_basis, bob_basis)
    counts = run_entanglement(qc, shots=shots)
    circuit_b64 = get_entanglement_circuit_b64(qc)

    formatted_counts = {k: v for k, v in sorted(counts.items())}

    return jsonify({
        "status": "success",
        "counts": formatted_counts,
        "circuit_b64": circuit_b64,
        "alice_basis": alice_basis,
        "bob_basis": bob_basis
    })

@app.route("/api/simulate/teleportation", methods=["GET"])
def simulate_teleportation():
    """
    Simulates quantum teleportation.
    Params:
      theta: angle in radians (default: 0.0)
      shots: number of simulation runs (default: 1024)
    """
    try:
        theta = float(request.args.get("theta", 0.0))
    except ValueError:
        theta = 0.0
        
    try:
        shots = int(request.args.get("shots", 1024))
    except ValueError:
        shots = 1024

    qc = create_teleportation(theta)
    counts = run_teleportation(qc, shots=shots)
    circuit_b64 = get_teleportation_circuit_b64(qc)

    formatted_counts = {k: v for k, v in sorted(counts.items())}

    # Calculate theoretical probabilities for verification
    # Alice's input state: cos(theta/2)|0> + sin(theta/2)|1>
    prob_0 = math.cos(theta / 2) ** 2
    prob_1 = math.sin(theta / 2) ** 2

    return jsonify({
        "status": "success",
        "counts": formatted_counts,
        "circuit_b64": circuit_b64,
        "theta": theta,
        "theoretical": {
            "0": round(prob_0, 4),
            "1": round(prob_1, 4)
        }
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
