import hashlib
import hmac
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def derive_bases(secret: bytes, challenge: bytes, count: int) -> list[int]:
    """
    Derives a sequence of basis choices (0 for Z, 1 for X) from a shared secret and a challenge
    using HMAC-SHA256. If count is greater than 256, it uses a counter-based KDF approach.
    """
    bases = []
    counter = 0
    while len(bases) < count:
        # Use HMAC-SHA256 to generate pseudorandom bytes
        h = hmac.new(secret, challenge + counter.to_bytes(4, 'big'), hashlib.sha256)
        digest = h.digest()
        
        # Convert digest bytes to bits
        for byte in digest:
            for bit_pos in range(8):
                if len(bases) < count:
                    # Extract bit from MSB to LSB
                    bit = (byte >> (7 - bit_pos)) & 1
                    bases.append(bit)
                else:
                    break
        counter += 1
    return bases

def derive_aes_key(sifted_key_bits: list[int]) -> bytes:
    """
    Hashes the sifted key bits from BB84 using SHA-256 to derive a uniform 256-bit AES key.
    """
    # Convert list of 0/1 bits to a byte string
    bit_str = "".join(str(b) for b in sifted_key_bits)
    return hashlib.sha256(bit_str.encode('utf-8')).digest()

def encrypt_payload(aes_key: bytes, plaintext: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypts a plaintext string using AES-256-GCM.
    Returns: (ciphertext, nonce, tag)
    """
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for GCM
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    
    # In cryptography, encrypt returns ciphertext + 16-byte tag
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]
    return ciphertext, nonce, tag

def decrypt_payload(aes_key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes) -> str:
    """
    Decrypts a ciphertext using AES-256-GCM.
    Returns the decrypted plaintext string.
    """
    aesgcm = AESGCM(aes_key)
    ciphertext_with_tag = ciphertext + tag
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    return decrypted_bytes.decode('utf-8')
