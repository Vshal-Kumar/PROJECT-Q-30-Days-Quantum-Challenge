# Quantum Security Toolkit

A complete, runnable simulation of the **BB84 Quantum Key Distribution (QKD)
protocol**, built with [Qiskit](https://www.ibm.com/quantum/qiskit) and
Qiskit Aer. The toolkit models Alice and Bob exchanging a secret key over a
simulated quantum channel, an eavesdropper ("Eve") performing an
intercept-resend attack, and automatic eavesdropping detection via
Quantum Bit Error Rate (QBER) analysis.

## Project Overview

BB84, introduced by Bennett and Brassard in 1984, is the original and most
widely studied quantum key distribution protocol. Its security rests on a
core principle of quantum mechanics: **measuring a quantum system in the
wrong basis disturbs it**. This lets two parties detect the presence of an
eavesdropper on their quantum channel, something impossible with purely
classical key exchange.

This toolkit simulates the full protocol end to end:

1. **Alice** generates random bits and random encoding bases, and prepares
   a qubit for each bit (computational or Hadamard basis).
2. The qubits travel across a simulated **quantum channel** to Bob —
   optionally passing through **Eve**, who intercepts, measures, and
   resends each qubit.
3. **Bob** independently chooses random measurement bases and measures
   each incoming qubit.
4. Alice and Bob **publicly compare bases** (not values) over a classical
   channel and keep only the bits where their bases matched ("sifting").
5. They **sacrifice a random sample** of the sifted key, compare it
   publicly, and compute the **QBER**. If QBER exceeds a security
   threshold (11%, the standard BB84 bound), an eavesdropper is declared
   present and the key is discarded. Otherwise, the remaining sifted bits
   become the **shared secret key**.
6. Results are visualized with Matplotlib.

## Folder Structure

```
QuantumSecurityToolkit/
├── bb84.py           # Core protocol: Alice, Bob, channels, encoding, measurement, sifting
├── attack.py         # Eve: intercept-resend attack implementation
├── detect.py         # QBER calculation and eavesdropping detection
├── app.py            # Main entry point: runs the simulation and generates plots
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Requirements

- Python 3.11+
- qiskit
- qiskit-aer
- numpy
- matplotlib

See `requirements.txt` for pinned versions.

## Installation

```bash
# (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Simulation

Run without an eavesdropper (safe channel):

```bash
python app.py --n 100 --seed 42
```

Run **with** Eve performing an intercept-resend attack:

```bash
python app.py --n 100 --seed 42 --eve
```

### Command-line options

| Flag       | Description                                         | Default             |
|------------|------------------------------------------------------|----------------------|
| `--n`      | Number of qubits Alice sends                          | `100`                |
| `--eve`    | Enable Eve's intercept-resend attack                   | off                  |
| `--seed`   | Random seed for reproducibility                        | `42`                 |
| `--output` | Path to save the results visualization (PNG)            | `bb84_results.png`   |

## Expected Output

The script prints a step-by-step protocol trace followed by a detection
report, for example:

```
============================================================
QUANTUM SECURITY TOOLKIT — BB84 QKD SIMULATION
============================================================
Number of qubits : 100
Eve present      : False
Random seed      : 42

[1] Alice generated random bits and bases, and encoded her qubits.
[2] Qubits traveled undisturbed over the quantum channel.
[3] Bob chose random measurement bases and measured the incoming qubits.
[4] Basis reconciliation complete: 48/100 bases matched (48.0%).
[5] Public error estimation and eavesdropping detection complete.

============================================================
EAVESDROPPING DETECTION REPORT
============================================================
Compared bits (public sample) : 24
Mismatched bits (errors)      : 0
Quantum Bit Error Rate (QBER)  : 0.0000 (0.00%)
Security threshold             : 0.1100 (11.00%)
------------------------------------------------------------
STATUS: Safe Communication
============================================================
Final shared secret key length : 24 bits

Visualization saved to: bb84_results.png
```

With `--eve` enabled, roughly a quarter of the sifted bits will mismatch
(because Eve guesses the wrong basis about half the time, and a wrong
basis choice yields a random, 50%-error outcome at Bob), pushing the QBER
to around 25–33% — far above the 11% threshold — and producing:

```
STATUS: Eavesdropper Detected
```

## Example Output

A sample run on 100 qubits produced:

| Scenario     | Bases Matched | QBER   | Result                 |
|--------------|----------------|--------|--------------------------|
| No Eve       | 48/100         | 0.00%  | Safe Communication       |
| With Eve     | 48/100         | 33.33% | Eavesdropper Detected    |

## Screenshots

The generated visualization (`bb84_results.png` or the path passed to
`--output`) contains six panels:

1. **Alice: Bits & Encoded States** — Alice's raw bits with their
   corresponding ket-notation quantum states (`|0>`, `|1>`, `|+>`, `|->`).
2. **Basis Comparison** — Alice's vs. Bob's basis choices per qubit, with
   matches marked.
3. **Sifted Key Comparison** — Alice's vs. Bob's sifted key bits side by
   side, with mismatches highlighted in red.
4. **QBER Chart** — measured QBER plotted against the 11% security
   threshold.
5. **Detection Status** — a color-coded "Safe Communication" or
   "Eavesdropper Detected" banner.
6. **Summary** — qubit counts, matched bases, compared bits, errors, and
   final key length.

Place the generated PNG screenshots in this section (e.g.
`docs/safe_run.png`, `docs/eve_run.png`) when documenting new runs.

## How the Attack Detection Works

Eve cannot clone an unknown quantum state (the **no-cloning theorem**), so
to learn any information she must measure each qubit — which requires
guessing a basis. When her guess is wrong (~50% of the time), the state
she forwards to Bob is effectively randomized in the basis Alice actually
used. Consequently, whenever Alice and Bob's bases matched but Eve's did
not, Bob's measurement has a 50% chance of disagreeing with Alice's
original bit. This yields an expected QBER of about **25%** under a full
intercept-resend attack — far above the ~11% threshold tolerated for
natural channel noise, making the attack statistically detectable with a
public sample of compared bits.

## License

Provided for educational purposes as part of the Project-Q Quantum
Security Toolkit assignment.
