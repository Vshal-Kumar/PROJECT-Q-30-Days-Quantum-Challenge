"""
app.py
------
Main entry point for the Quantum Security Toolkit.

Runs a complete end-to-end simulation of the BB84 Quantum Key
Distribution protocol between Alice and Bob, optionally in the
presence of an eavesdropper (Eve) performing an intercept-resend
attack, and produces:

    1. A full console report of every protocol stage.
    2. A multi-panel Matplotlib visualization saved to disk.

Usage:
    python app.py                     # run without Eve (safe channel)
    python app.py --eve               # run with Eve intercepting
    python app.py --n 200 --seed 42   # customize qubit count / seed
"""

from __future__ import annotations

import argparse
import sys

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend, safe for headless runs.
import matplotlib.pyplot as plt
import numpy as np

from bb84 import Alice, Bob, QuantumChannel, sift_key
from attack import Eve
from detect import analyze_key, print_detection_report, DEFAULT_QBER_THRESHOLD


def run_bb84_protocol(n_qubits: int, eve_present: bool, seed: int | None):
    """
    Execute the full BB84 protocol pipeline.

    Args:
        n_qubits: Number of qubits Alice will prepare and send.
        eve_present: Whether an eavesdropper intercepts the channel.
        seed: Optional RNG seed for reproducibility.

    Returns:
        Dictionary containing every intermediate and final artifact of
        the run, used both for the console report and the plots.
    """
    print("=" * 60)
    print("QUANTUM SECURITY TOOLKIT — BB84 QKD SIMULATION")
    print("=" * 60)
    print(f"Number of qubits : {n_qubits}")
    print(f"Eve present      : {eve_present}")
    print(f"Random seed      : {seed}")
    print()

    # ---- Step 1: Alice prepares her random bits, bases, and qubits ----
    alice = Alice(n_qubits, seed=seed)
    print("[1] Alice generated random bits and bases, and encoded her qubits.")

    # ---- Step 2: Transmission over the quantum channel (with optional Eve) ----
    qubits_in_transit = QuantumChannel.transmit(alice.send_qubits())

    eve = None
    if eve_present:
        eve = Eve(n_qubits, seed=None if seed is None else seed + 100)
        qubits_in_transit = eve.intercept_and_resend(qubits_in_transit)
        print("[2] Eve intercepted every qubit, measured it, and resent a replacement.")
    else:
        print("[2] Qubits traveled undisturbed over the quantum channel.")

    # ---- Step 3: Bob receives and measures in his own random bases ----
    bob = Bob(n_qubits, seed=None if seed is None else seed + 200)
    bob_bits = bob.receive_and_measure(qubits_in_transit)
    print("[3] Bob chose random measurement bases and measured the incoming qubits.")

    # ---- Step 4: Public basis reconciliation (sifting) ----
    matching_indices, alice_sifted, bob_sifted = sift_key(
        alice.bases, bob.bases, alice.bits, bob_bits
    )
    print(
        f"[4] Basis reconciliation complete: "
        f"{len(matching_indices)}/{n_qubits} bases matched "
        f"({len(matching_indices) / n_qubits * 100:.1f}%)."
    )

    # ---- Step 5: QBER estimation and eavesdropping detection ----
    result = analyze_key(
        alice_sifted,
        bob_sifted,
        sample_fraction=0.5,
        threshold=DEFAULT_QBER_THRESHOLD,
        seed=None if seed is None else seed + 300,
    )
    print("[5] Public error estimation and eavesdropping detection complete.")
    print()
    print_detection_report(result)

    return {
        "n_qubits": n_qubits,
        "alice": alice,
        "bob": bob,
        "eve": eve,
        "matching_indices": matching_indices,
        "alice_sifted": alice_sifted,
        "bob_sifted": bob_sifted,
        "result": result,
    }


def _encoded_state_labels(bits: np.ndarray, bases: np.ndarray) -> list[str]:
    """Build human-readable ket labels (e.g. '|0>', '|+>') for each bit/basis pair."""
    labels = []
    for bit, basis in zip(bits, bases):
        if basis == "Z":
            labels.append("|0>" if bit == 0 else "|1>")
        else:
            labels.append("|+>" if bit == 0 else "|->")
    return labels


def visualize_results(run_data: dict, output_path: str, display_limit: int = 40) -> None:
    """
    Produce a multi-panel Matplotlib figure summarizing the BB84 run
    and save it to disk.

    Panels:
        1. Alice's bits vs. bases (first `display_limit` qubits)
        2. Bob's bases vs. Alice's bases (basis matching)
        3. Sifted key comparison (Alice vs. Bob) and error locations
        4. QBER bar chart against the security threshold
        5. Eavesdropping detection status banner
        6. Summary bit counts (sent / sifted / final key / errors)

    Args:
        run_data: Dictionary returned by run_bb84_protocol.
        output_path: File path to save the resulting PNG figure.
        display_limit: Max number of qubits to show in the detailed
            per-qubit panels (for readability with large n).
    """
    alice = run_data["alice"]
    bob = run_data["bob"]
    result = run_data["result"]
    matching_indices = run_data["matching_indices"]
    alice_sifted = run_data["alice_sifted"]
    bob_sifted = run_data["bob_sifted"]
    n = run_data["n_qubits"]
    limit = min(n, display_limit)

    fig = plt.figure(figsize=(16, 12))
    fig.suptitle("Quantum Security Toolkit — BB84 QKD Simulation Results", fontsize=16, fontweight="bold")
    gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.3)

    # --- Panel 1: Alice's bits, bases, and encoded quantum states ---
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(limit)
    ax1.scatter(x, alice.bits[:limit], c="tab:blue", label="Alice's Bits", zorder=3)
    state_labels = _encoded_state_labels(alice.bits[:limit], alice.bases[:limit])
    for xi, yi, lbl in zip(x, alice.bits[:limit], state_labels):
        ax1.annotate(lbl, (xi, yi), textcoords="offset points", xytext=(0, 8), fontsize=7, ha="center")
    ax1.set_title(f"Alice: Bits & Encoded States (first {limit})")
    ax1.set_xlabel("Qubit index")
    ax1.set_ylabel("Bit value")
    ax1.set_yticks([0, 1])
    ax1.grid(alpha=0.3)

    # --- Panel 2: Basis comparison (Alice vs Bob) ---
    ax2 = fig.add_subplot(gs[0, 1])
    alice_basis_numeric = np.where(alice.bases[:limit] == "Z", 0, 1)
    bob_basis_numeric = np.where(bob.bases[:limit] == "Z", 0, 1)
    ax2.plot(x, alice_basis_numeric, "o-", label="Alice's Basis", color="tab:blue", alpha=0.8)
    ax2.plot(x, bob_basis_numeric, "s--", label="Bob's Basis", color="tab:orange", alpha=0.8)
    match_mask = alice.bases[:limit] == bob.bases[:limit]
    ax2.scatter(x[match_mask], np.full(match_mask.sum(), 1.5), marker="*", color="green", s=60, label="Match")
    ax2.set_title(f"Basis Comparison — Alice vs. Bob (first {limit})")
    ax2.set_xlabel("Qubit index")
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Z", "X"])
    ax2.set_ylim(-0.5, 2)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(alpha=0.3)

    # --- Panel 3: Sifted key comparison ---
    ax3 = fig.add_subplot(gs[1, :])
    sift_limit = min(len(alice_sifted), display_limit)
    sx = np.arange(sift_limit)
    width = 0.35
    ax3.bar(sx - width / 2, alice_sifted[:sift_limit], width, label="Alice Sifted Key", color="tab:blue")
    ax3.bar(sx + width / 2, bob_sifted[:sift_limit], width, label="Bob Sifted Key", color="tab:orange")
    mismatches = np.where(alice_sifted[:sift_limit] != bob_sifted[:sift_limit])[0]
    for m in mismatches:
        ax3.axvspan(m - 0.5, m + 0.5, color="red", alpha=0.15)
    ax3.set_title(f"Sifted Key Comparison (first {sift_limit} of {len(alice_sifted)} sifted bits) — "
                  f"red bands mark mismatches")
    ax3.set_xlabel("Sifted key index")
    ax3.set_ylabel("Bit value")
    ax3.set_yticks([0, 1])
    ax3.legend(loc="upper right", fontsize=8)
    ax3.grid(alpha=0.3)

    # --- Panel 4: QBER vs threshold ---
    ax4 = fig.add_subplot(gs[2, 0])
    bars = ax4.bar(
        ["Measured QBER", "Security Threshold"],
        [result.qber, result.threshold],
        color=["crimson" if result.eavesdropper_detected else "seagreen", "gray"],
    )
    for bar in bars:
        height = bar.get_height()
        ax4.annotate(f"{height * 100:.2f}%", (bar.get_x() + bar.get_width() / 2, height),
                     textcoords="offset points", xytext=(0, 5), ha="center", fontsize=9)
    ax4.set_ylim(0, max(0.3, result.qber * 1.3, result.threshold * 1.3))
    ax4.set_title("Quantum Bit Error Rate (QBER)")
    ax4.set_ylabel("Error rate")
    ax4.grid(alpha=0.3, axis="y")

    # --- Panel 5: Detection status + summary counts ---
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.axis("off")
    status_color = "crimson" if result.eavesdropper_detected else "seagreen"
    ax5.text(
        0.5, 0.75, result.status_message,
        ha="center", va="center", fontsize=20, fontweight="bold", color=status_color,
        transform=ax5.transAxes,
    )
    summary_lines = [
        f"Qubits sent:        {n}",
        f"Bases matched:      {len(matching_indices)}",
        f"Bits compared:      {result.compared_bits}",
        f"Errors found:       {result.error_count}",
        f"Final key length:   {len(result.final_key_alice)}",
    ]
    ax5.text(
        0.5, 0.30, "\n".join(summary_lines),
        ha="center", va="center", fontsize=11, family="monospace",
        transform=ax5.transAxes,
    )
    ax5.set_title("Summary")

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nVisualization saved to: {output_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the toolkit."""
    parser = argparse.ArgumentParser(
        description="Quantum Security Toolkit — BB84 QKD Simulation"
    )
    parser.add_argument(
        "--n", type=int, default=100, help="Number of qubits to simulate (default: 100)"
    )
    parser.add_argument(
        "--eve", action="store_true", help="Enable Eve's intercept-resend attack"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output", type=str, default="bb84_results.png",
        help="Path to save the results visualization (default: bb84_results.png)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    args = parse_args(argv)
    run_data = run_bb84_protocol(n_qubits=args.n, eve_present=args.eve, seed=args.seed)
    visualize_results(run_data, output_path=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
