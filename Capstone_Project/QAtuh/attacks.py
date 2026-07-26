import time
from .channel import QuantumChannel
from .auth import EPRAuthenticator
from .key_exchange import BB84KeyExchange
from .crypto import encrypt_payload, decrypt_payload

def run_simulation(
    secret: bytes,
    alice_secret: bytes = None,
    noise_rate: float = 0.0,
    epr_size: int = 100,
    bb84_size: int = 100,
    attack_type: str = None
) -> dict:
    """
    Orchestrates the entire quantum authentication and key exchange simulation sequence.

    Args:
        secret (bytes): The server's pre-shared secret key.
        alice_secret (bytes, optional): Alice's secret key (matches Bob's by default).
        noise_rate (float): Channel depolarizing noise probability (0.0 to 1.0).
        epr_size (int): Batch size of EPR pairs for identity authentication.
        bb84_size (int): Number of qubits to send in BB84 key exchange.
        attack_type (str, optional): The scenario to simulate.
            Supported: None, 'eavesdrop', 'impersonate', 'replay', 'wrong_secret'.

    Returns:
        dict: Standardized report of simulation events, metrics, and logs.
    """
    logs = []
    logs.append(f"=== Starting Quantum Security Simulation ===")
    logs.append(f"Scenario: {attack_type if attack_type else 'Normal (No Attack)'}")
    logs.append(f"Noise Rate: {noise_rate:.1%}")
    logs.append(f"EPR Authentication Batch: {epr_size} pairs")
    logs.append(f"BB84 QKD Batch: {bb84_size} qubits")

    if alice_secret is None:
        if attack_type == 'wrong_secret':
            alice_secret = secret + b"_wrong_suffix"
        else:
            alice_secret = secret

    # 1. Setup Replay Data if needed
    replay_data = None
    if attack_type == 'replay':
        logs.append("[Replay Setup] Simulating previous clean session to record Alice's response...")
        clean_channel = QuantumChannel(noise_rate=0.0, attack_type=None)
        clean_auth = EPRAuthenticator(secret, batch_size=epr_size)
        clean_res = clean_auth.run_authentication(alice_secret=secret, channel=clean_channel)
        replay_data = clean_res['alice_results']
        logs.append(f"[Replay Setup] Successfully recorded {len(replay_data)} response bits.")

    # 2. Initialize Quantum Channel
    # For eavesdrop scenario, active interception occurs on the channel
    channel_attack = 'eavesdrop' if attack_type == 'eavesdrop' else None
    channel = QuantumChannel(noise_rate=noise_rate, attack_type=channel_attack)

    # 3. EPR Challenge-Response Authentication
    logs.append("\n--- Phase 1: EPR Challenge-Response Authentication ---")
    auth = EPRAuthenticator(secret, batch_size=epr_size)
    impersonate = (attack_type == 'impersonate')
    
    start_time = time.perf_counter()
    auth_res = auth.run_authentication(
        alice_secret=alice_secret,
        channel=channel,
        impersonate=impersonate,
        replay_data=replay_data
    )
    auth_duration = time.perf_counter() - start_time
    
    logs.append(f"EPR measurements computed in {auth_duration*1000:.2f} ms.")
    logs.append(f"Quantum Bit Error Rate (QBER): {auth_res['qber']:.2%}")
    
    if auth_res['authenticated']:
        logs.append("AUTHENTICATION SUCCESSFUL: Bob verified Alice's identity.")
    else:
        logs.append("AUTHENTICATION FAILED: Identity validation failed. Connection terminated.")
        return {
            'auth_success': False,
            'auth_qber': auth_res['qber'],
            'bb84_success': None,
            'bb84_qber': None,
            'session_key_derived': False,
            'encryption_success': None,
            'gate_count': auth_res['gate_count'],
            'depth': auth_res['depth'],
            'latency_ms': auth_duration * 1000,
            'logs': logs
        }

    # 4. BB84 Key Exchange
    logs.append("\n--- Phase 2: BB84 Quantum Key Distribution ---")
    bb84 = BB84KeyExchange(num_qubits=bb84_size)
    
    start_time = time.perf_counter()
    bb84_res = bb84.run_key_exchange(channel)
    bb84_duration = time.perf_counter() - start_time
    
    total_gate_count = auth_res['gate_count'] + bb84_res.get('gate_count', 0)
    total_depth = auth_res['depth'] + bb84_res.get('depth', 0)
    total_latency_ms = (auth_duration + bb84_duration) * 1000

    if not bb84_res['success']:
        logs.append(f"BB84 KEY EXCHANGE FAILED: {bb84_res['reason']}")
        return {
            'auth_success': True,
            'auth_qber': auth_res['qber'],
            'bb84_success': False,
            'bb84_qber': bb84_res.get('qber', None),
            'session_key_derived': False,
            'encryption_success': None,
            'gate_count': total_gate_count,
            'depth': total_depth,
            'latency_ms': total_latency_ms,
            'logs': logs
        }

    logs.append("BB84 KEY EXCHANGE SUCCESSFUL.")
    logs.append(f"QBER during Parameter Estimation: {bb84_res['qber']:.2%}")
    logs.append(f"Sifted Bits: {bb84_res['sifted_length']}")
    logs.append(f"Key Bits Remaining (after check bits): {bb84_res['key_bits_remaining']}")
    
    # 5. Symmetric Payload Encryption
    logs.append("\n--- Phase 3: Classical AES-GCM Encrypted Communication ---")
    aes_key = bb84_res['derived_key']
    test_message = "Confidential Capstone Project Data: Quantum Authentication verified."
    logs.append(f"Plaintext Payload: '{test_message}'")
    
    try:
        ciphertext, nonce, tag = encrypt_payload(aes_key, test_message)
        logs.append(f"Ciphertext: {ciphertext.hex()[:32]}...")
        logs.append(f"Tag: {tag.hex()} | Nonce: {nonce.hex()}")
        
        # Simulating transmission and decryption
        decrypted_msg = decrypt_payload(aes_key, ciphertext, nonce, tag)
        logs.append(f"Decrypted Payload: '{decrypted_msg}'")
        encryption_success = (decrypted_msg == test_message)
        logs.append("Payload verification: INTEGRITY VALIDATED.")
    except Exception as e:
        logs.append(f"AES decryption error: {str(e)}")
        encryption_success = False
        
    logs.append(f"=============================================")
    return {
        'auth_success': True,
        'auth_qber': auth_res['qber'],
        'bb84_success': True,
        'bb84_qber': bb84_res['qber'],
        'session_key_derived': True,
        'encryption_success': encryption_success,
        'gate_count': total_gate_count,
        'depth': total_depth,
        'latency_ms': total_latency_ms,
        'logs': logs
    }
