from flask import Flask, render_template, request, jsonify
import os
import sys
import secrets
from QAtuh.attacks import run_simulation
from QAtuh.metrics import collect_scenario_stats, generate_qber_vs_noise_plot, generate_detection_vs_batch_plot

app = Flask(__name__)

# Application state
current_secret = b"capstone_pre_shared_secret_key"
DIAGRAMS_DIR = os.path.join(app.root_path, "static", "diagrams")
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

@app.route('/')
def index():
    # Make sure default plots exist
    plot_noise = os.path.join(DIAGRAMS_DIR, "qber_vs_noise.png")
    plot_batch = os.path.join(DIAGRAMS_DIR, "detection_vs_batch_size.png")
    if not os.path.exists(plot_noise) or not os.path.exists(plot_batch):
        # Generate initial fast plots
        generate_qber_vs_noise_plot(current_secret, DIAGRAMS_DIR, iterations=5)
        generate_detection_vs_batch_plot(current_secret, DIAGRAMS_DIR, iterations=5)
        
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    global current_secret
    data = request.json or {}
    secret_str = data.get('secret', '')
    
    if not secret_str:
        # Generate a random 16-byte hex secret
        secret_str = secrets.token_hex(16)
        
    current_secret = secret_str.encode('utf-8')
    return jsonify({
        'success': True,
        'secret': secret_str
    })

@app.route('/api/simulate', methods=['POST'])
def simulate():
    global current_secret
    data = request.json or {}
    
    attack_type = data.get('attack_type', None)
    if attack_type == 'none':
        attack_type = None
        
    noise_rate = float(data.get('noise_rate', 0.02))
    epr_size = int(data.get('epr_size', 100))
    bb84_size = int(data.get('bb84_size', 100))
    
    # Run the simulation
    res = run_simulation(
        secret=current_secret,
        noise_rate=noise_rate,
        epr_size=epr_size,
        bb84_size=bb84_size,
        attack_type=attack_type
    )
    
    # Return serializable metrics (remove circuit object if present)
    response_data = {
        'auth_success': res['auth_success'],
        'auth_qber': res['auth_qber'],
        'bb84_success': res['bb84_success'],
        'bb84_qber': res['bb84_qber'],
        'session_key_derived': res['session_key_derived'],
        'encryption_success': res['encryption_success'],
        'gate_count': res['gate_count'],
        'depth': res['depth'],
        'latency_ms': res['latency_ms'],
        'logs': res['logs']
    }
    
    return jsonify(response_data)

@app.route('/api/benchmarks', methods=['GET'])
def get_benchmarks():
    global current_secret
    # Run a fast benchmark (10 iterations per scenario)
    stats = collect_scenario_stats(
        secret=current_secret,
        iterations=10,
        epr_size=100,
        bb84_size=100,
        noise_rate=0.02
    )
    
    # Regenerate the plots in the static/diagrams folder
    generate_qber_vs_noise_plot(current_secret, DIAGRAMS_DIR, iterations=5)
    generate_detection_vs_batch_plot(current_secret, DIAGRAMS_DIR, iterations=5)
    
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
