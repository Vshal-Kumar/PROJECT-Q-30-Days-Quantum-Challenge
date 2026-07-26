import os
import time
import numpy as np
import matplotlib.pyplot as plt
from .attacks import run_simulation

def collect_scenario_stats(secret: bytes, iterations: int = 30, epr_size: int = 100, bb84_size: int = 100, noise_rate: float = 0.02) -> dict:
    """
    Collects performance statistics for all 5 scenarios over multiple iterations.
    """
    scenarios = {
        'normal': {'attack_type': None, 'alice_secret': secret},
        'eavesdrop': {'attack_type': 'eavesdrop', 'alice_secret': secret},
        'impersonate': {'attack_type': 'impersonate', 'alice_secret': secret},
        'replay': {'attack_type': 'replay', 'alice_secret': secret},
        'wrong_secret': {'attack_type': 'wrong_secret', 'alice_secret': secret + b"_wrong"}
    }

    results = {}
    for name, params in scenarios.items():
        auth_successes = 0
        bb84_successes = 0
        qbers_auth = []
        qbers_bb84 = []
        latencies = []
        gate_counts = []
        depths = []
        keys_derived = 0

        for _ in range(iterations):
            res = run_simulation(
                secret=secret,
                alice_secret=params['alice_secret'],
                noise_rate=noise_rate,
                epr_size=epr_size,
                bb84_size=bb84_size,
                attack_type=params['attack_type']
            )
            
            if res['auth_success']:
                auth_successes += 1
            if res['auth_qber'] is not None:
                qbers_auth.append(res['auth_qber'])
            
            if res['bb84_success'] is not None:
                qbers_bb84.append(res['bb84_qber'])
                if res['bb84_success']:
                    bb84_successes += 1
            
            if res['session_key_derived']:
                keys_derived += 1
                
            latencies.append(res['latency_ms'])
            gate_counts.append(res['gate_count'])
            depths.append(res['depth'])

        # Compute averages
        results[name] = {
            'auth_success_rate': auth_successes / iterations,
            'avg_auth_qber': np.mean(qbers_auth) if qbers_auth else 0.0,
            'bb84_success_rate': bb84_successes / iterations if any(x is not None for x in qbers_bb84) else 0.0,
            'avg_bb84_qber': np.mean(qbers_bb84) if qbers_bb84 else 0.0,
            'key_derivation_rate': keys_derived / iterations,
            'avg_latency_ms': np.mean(latencies),
            'avg_gate_count': np.mean(gate_counts),
            'avg_depth': np.mean(depths),
            # An attack is correctly detected if the system rejects authentication or key exchange
            'detection_rate': (1.0 - (keys_derived / iterations)) if name != 'normal' else 0.0
        }
    return results

def generate_qber_vs_noise_plot(secret: bytes, output_dir: str, iterations: int = 15):
    """
    Simulates and plots QBER vs Channel Noise for Normal and Eavesdropping scenarios.
    """
    noise_levels = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    normal_qber = []
    eavesdrop_qber = []

    for noise in noise_levels:
        normal_runs = []
        eavesdrop_runs = []
        for _ in range(iterations):
            # Normal
            res_n = run_simulation(secret=secret, noise_rate=noise, attack_type=None, epr_size=100)
            normal_runs.append(res_n['auth_qber'])
            # Eavesdropping
            res_e = run_simulation(secret=secret, noise_rate=noise, attack_type='eavesdrop', epr_size=100)
            eavesdrop_runs.append(res_e['auth_qber'])
            
        normal_qber.append(np.mean(normal_runs))
        eavesdrop_qber.append(np.mean(eavesdrop_runs))

    plt.figure(figsize=(8, 5))
    plt.plot(noise_levels, normal_qber, 'o-', label='Normal (Honest Alice & Bob)', color='#2e7d32', linewidth=2)
    plt.plot(noise_levels, eavesdrop_qber, 's-', label='Eavesdropping (Eve intercepting)', color='#c62828', linewidth=2)
    
    # Draw authentication threshold (15% QBER)
    plt.axhline(y=0.15, color='#d84315', linestyle='--', label='Authentication Threshold (15% QBER)')
    # Draw theoretical BB84 threshold (11% QBER)
    plt.axhline(y=0.11, color='#1565c0', linestyle=':', label='BB84 Security Threshold (11% QBER)')
    
    plt.title('Quantum Bit Error Rate (QBER) vs. Quantum Channel Noise', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('Channel Depolarizing Noise Rate', fontsize=10)
    plt.ylabel('Measured QBER', fontsize=10)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='best', framealpha=0.9)
    plt.ylim(-0.02, 0.55)
    
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'qber_vs_noise.png'), dpi=300, bbox_inches='tight')
    plt.close()

def generate_detection_vs_batch_plot(secret: bytes, output_dir: str, iterations: int = 20):
    """
    Plots the Attack Detection Rate vs. EPR Batch Size for an Impersonation Attack.
    This demonstrates why single-shot verification fails and how batching enables high-confidence detection.
    """
    batch_sizes = [5, 10, 20, 30, 50, 100, 150]
    impersonation_detection = []
    replay_detection = []

    for size in batch_sizes:
        imp_detects = 0
        rep_detects = 0
        for _ in range(iterations):
            # Impersonation
            res_i = run_simulation(secret=secret, noise_rate=0.02, epr_size=size, attack_type='impersonate')
            if not res_i['auth_success']:
                imp_detects += 1
            # Replay
            res_r = run_simulation(secret=secret, noise_rate=0.02, epr_size=size, attack_type='replay')
            if not res_r['auth_success']:
                rep_detects += 1
                
        impersonation_detection.append(imp_detects / iterations)
        replay_detection.append(rep_detects / iterations)

    plt.figure(figsize=(8, 5))
    plt.plot(batch_sizes, impersonation_detection, 'o-', label='Impersonation Detection Rate', color='#e65100', linewidth=2)
    plt.plot(batch_sizes, replay_detection, '^--', label='Replay Attack Detection Rate', color='#311b92', linewidth=2)
    
    plt.title('Attack Detection Confidence vs. EPR Batch Size', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('EPR Pair Batch Size (N)', fontsize=10)
    plt.ylabel('Detection Probability (True Positive Rate)', fontsize=10)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='lower right', framealpha=0.9)
    plt.ylim(-0.05, 1.05)
    
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'detection_vs_batch_size.png'), dpi=300, bbox_inches='tight')
    plt.close()
