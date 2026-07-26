import pytest
import os
from QAtuh.crypto import derive_bases, encrypt_payload, decrypt_payload, derive_aes_key
from QAtuh.channel import QuantumChannel
from QAtuh.auth import EPRAuthenticator
from QAtuh.key_exchange import BB84KeyExchange
from QAtuh.attacks import run_simulation
from cryptography.exceptions import InvalidTag

def test_crypto_basis_derivation():
    secret = b"my_secret_key_123"
    challenge = b"random_challenge_456"
    
    # Check correct length and values
    bases1 = derive_bases(secret, challenge, 50)
    assert len(bases1) == 50
    assert all(b in [0, 1] for b in bases1)
    
    # Check determinism
    bases2 = derive_bases(secret, challenge, 50)
    assert bases1 == bases2
    
    # Check that change in challenge changes bases
    bases3 = derive_bases(secret, b"different_challenge", 50)
    assert bases1 != bases3

def test_crypto_aes_gcm():
    key = os.urandom(32)
    message = "Hello, this is a test quantum payload!"
    
    # Encrypt and decrypt
    ciphertext, nonce, tag = encrypt_payload(key, message)
    decrypted = decrypt_payload(key, ciphertext, nonce, tag)
    assert decrypted == message
    
    # Test decryption failure with incorrect key
    wrong_key = os.urandom(32)
    with pytest.raises(InvalidTag):
        decrypt_payload(wrong_key, ciphertext, nonce, tag)

    # Test decryption failure with tampered ciphertext
    tampered_ciphertext = bytearray(ciphertext)
    tampered_ciphertext[0] ^= 1 # flip one bit
    with pytest.raises(InvalidTag):
        decrypt_payload(key, bytes(tampered_ciphertext), nonce, tag)

def test_auth_success():
    secret = b"correct_secret"
    auth = EPRAuthenticator(secret, batch_size=20, threshold=0.10)
    channel = QuantumChannel(noise_rate=0.0)
    
    # Honest Alice and Bob on noiseless channel should get 0% QBER and succeed
    res = auth.run_authentication(alice_secret=secret, channel=channel)
    assert res['authenticated'] is True
    assert res['qber'] == 0.0
    assert res['alice_results'] == res['bob_results']

def test_auth_failure_wrong_secret():
    secret = b"correct_secret"
    wrong_secret = b"wrong_secret"
    auth = EPRAuthenticator(secret, batch_size=50, threshold=0.15)
    channel = QuantumChannel(noise_rate=0.0)
    
    # Alice with wrong secret should fail
    res = auth.run_authentication(alice_secret=wrong_secret, channel=channel)
    assert res['authenticated'] is False
    # Expected QBER is around 50% since bases mismatch
    assert res['qber'] > 0.20

def test_auth_failure_impersonate():
    secret = b"correct_secret"
    auth = EPRAuthenticator(secret, batch_size=50, threshold=0.15)
    channel = QuantumChannel(noise_rate=0.0)
    
    # Eve trying to impersonate Alice should fail
    res = auth.run_authentication(alice_secret=secret, channel=channel, impersonate=True)
    assert res['authenticated'] is False
    assert res['qber'] > 0.20

def test_bb84_key_exchange_noiseless():
    bb84 = BB84KeyExchange(num_qubits=40, threshold=0.11)
    channel = QuantumChannel(noise_rate=0.0)
    
    # Noiseless BB84 should succeed
    res = bb84.run_key_exchange(channel)
    assert res['success'] is True
    assert res['qber'] == 0.0
    assert res['derived_key'] is not None
    assert len(res['derived_key']) == 32 # 256-bit AES key

def test_bb84_key_exchange_noisy():
    bb84 = BB84KeyExchange(num_qubits=200, threshold=0.11)
    # High noise (80%) should trigger key exchange abort
    channel = QuantumChannel(noise_rate=0.80)
    
    res = bb84.run_key_exchange(channel)
    assert res['success'] is False
    assert "exceeds security threshold" in res['reason']


def test_run_simulation_full():
    secret = b"full_test_secret"
    
    # Test normal flow
    res = run_simulation(secret=secret, noise_rate=0.01, epr_size=50, bb84_size=50)
    assert res['auth_success'] is True
    assert res['bb84_success'] is True
    assert res['session_key_derived'] is True
    assert res['encryption_success'] is True
    
    # Test wrong secret flow
    res_wrong = run_simulation(secret=secret, alice_secret=b"wrong", noise_rate=0.01, epr_size=50, bb84_size=50)
    assert res_wrong['auth_success'] is False
    assert res_wrong['session_key_derived'] is False
