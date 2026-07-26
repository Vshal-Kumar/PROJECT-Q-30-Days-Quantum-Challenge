#!/usr/bin/env python3
import argparse
import sys
import os
from QAtuh.attacks import run_simulation
from QAtuh.metrics import collect_scenario_stats, generate_qber_vs_noise_plot, generate_detection_vs_batch_plot

# Set default parameters
DEFAULT_SECRET = b"capstone_pre_shared_secret_key"
DEFAULT_EPR_SIZE = 100
DEFAULT_BB84_SIZE = 100
DEFAULT_NOISE_RATE = 0.02
DIAGRAMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrams")

def print_banner():
    print("=" * 60)
    print("      QUANTUM SECURITY HANDSHAKE SIMULATION FRAMEWORK      ")
    print("           EPR Authentication + BB84 Key Exchange          ")
    print("=" * 60)

def cmd_run_flow(args):
    print_banner()
    res = run_simulation(
        secret=DEFAULT_SECRET,
        noise_rate=args.noise_rate,
        epr_size=args.epr_size,
        bb84_size=args.bb84_size,
        attack_type=None
    )
    for log in res['logs']:
        print(log)

def cmd_run_attack(args):
    print_banner()
    attack_type = args.type
    if attack_type not in ['eavesdrop', 'impersonate', 'replay', 'wrong_secret']:
        print(f"Error: Unknown attack type '{attack_type}'", file=sys.stderr)
        sys.exit(1)
        
    res = run_simulation(
        secret=DEFAULT_SECRET,
        noise_rate=args.noise_rate,
        epr_size=args.epr_size,
        bb84_size=args.bb84_size,
        attack_type=attack_type
    )
    for log in res['logs']:
        print(log)

def cmd_benchmark(args):
    print_banner()
    print(f"Running benchmarks ({args.iterations} iterations per scenario)...")
    print(f"EPR Size: {args.epr_size} | BB84 Qubits: {args.bb84_size} | Noise Rate: {args.noise_rate:.1%}")
    print("-" * 60)
    
    # Run stats
    stats = collect_scenario_stats(
        secret=DEFAULT_SECRET,
        iterations=args.iterations,
        epr_size=args.epr_size,
        bb84_size=args.bb84_size,
        noise_rate=args.noise_rate
    )
    
    # Print Markdown Table
    print("\n### Benchmark Results Table")
    print("| Scenario | Auth Success | Avg Auth QBER | BB84 Success | Avg BB84 QBER | Key Derived | Avg Latency |")
    print("|---|---|---|---|---|---|---|")
    for name, data in stats.items():
        auth_succ = f"{data['auth_success_rate']:.1%}"
        auth_qber = f"{data['avg_auth_qber']:.2%}"
        bb84_succ = f"{data['bb84_success_rate']:.1%}" if data['bb84_success_rate'] is not None else "N/A"
        bb84_qber = f"{data['avg_bb84_qber']:.2%}" if data['avg_bb84_qber'] > 0 else "N/A"
        key_rate = f"{data['key_derivation_rate']:.1%}"
        latency = f"{data['avg_latency_ms']:.2f} ms"
        print(f"| {name.capitalize()} | {auth_succ} | {auth_qber} | {bb84_succ} | {bb84_qber} | {key_rate} | {latency} |")
        
    print("\nGenerating plotting diagrams in 'diagrams/' folder...")
    generate_qber_vs_noise_plot(DEFAULT_SECRET, DIAGRAMS_DIR, iterations=args.plot_iterations)
    print("-> Generated diagrams/qber_vs_noise.png")
    generate_detection_vs_batch_plot(DEFAULT_SECRET, DIAGRAMS_DIR, iterations=args.plot_iterations)
    print("-> Generated diagrams/detection_vs_batch_size.png")
    print("\nBenchmarks completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Quantum authentication and key exchange simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run-flow subparser
    run_parser = subparsers.add_parser("run-flow", help="Run standard noiseless/noisy handshake flow")
    run_parser.add_argument("--noise-rate", type=float, default=DEFAULT_NOISE_RATE, help="Depolarizing noise rate")
    run_parser.add_argument("--epr-size", type=int, default=DEFAULT_EPR_SIZE, help="Authentication EPR batch size")
    run_parser.add_argument("--bb84-size", type=int, default=DEFAULT_BB84_SIZE, help="BB84 QKD batch size")
    run_parser.set_defaults(func=cmd_run_flow)

    # run-attack subparser
    attack_parser = subparsers.add_parser("run-attack", help="Run specific attack scenario")
    attack_parser.add_argument("type", choices=['eavesdrop', 'impersonate', 'replay', 'wrong_secret'], help="Attack type")
    attack_parser.add_argument("--noise-rate", type=float, default=DEFAULT_NOISE_RATE, help="Depolarizing noise rate")
    attack_parser.add_argument("--epr-size", type=int, default=DEFAULT_EPR_SIZE, help="Authentication EPR batch size")
    attack_parser.add_argument("--bb84-size", type=int, default=DEFAULT_BB84_SIZE, help="BB84 QKD batch size")
    attack_parser.set_defaults(func=cmd_run_attack)

    # benchmark subparser
    bench_parser = subparsers.add_parser("benchmark", help="Run comprehensive statistical benchmark")
    bench_parser.add_argument("--iterations", type=int, default=30, help="Number of benchmark iterations")
    bench_parser.add_argument("--plot-iterations", type=int, default=15, help="Number of iterations for plot simulations")
    bench_parser.add_argument("--epr-size", type=int, default=DEFAULT_EPR_SIZE, help="EPR batch size")
    bench_parser.add_argument("--bb84-size", type=int, default=DEFAULT_BB84_SIZE, help="BB84 batch size")
    bench_parser.add_argument("--noise-rate", type=float, default=DEFAULT_NOISE_RATE, help="Baseline noise rate")
    bench_parser.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
