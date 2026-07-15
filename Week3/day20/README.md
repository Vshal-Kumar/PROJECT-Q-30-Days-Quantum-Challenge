# PQC Secure Chat Demo (ML-KEM-768 + ML-DSA-65 + ChaCha20-Poly1305)

A minimal client/server chat over TCP that demonstrates a hybrid-style
post-quantum handshake using **liboqs**, followed by classical
**ChaCha20-Poly1305** AEAD for the actual traffic. Verified working
end-to-end (build + live handshake + message exchange) against liboqs
built from the `open-quantum-safe/liboqs` GitHub `main` branch.

## Protocol

```
 SERVER                                            CLIENT
 ------                                            ------
 Long-term ML-DSA-65 keypair (dsa_pk, dsa_sk)
 dsa_pk written to server_dsa_pub.key      ---(out of band, once)--->  loads dsa_pk

 accept()  <----------------------------------------------- connect()

 Ephemeral ML-KEM-768 keypair (kem_pk, kem_sk)
 sig = Sign(dsa_sk, kem_pk)

           ------ kem_pk, sig ------------------------------------->  verify(dsa_pk, kem_pk, sig)
                                                                       abort if verification fails
                                                                       (ct, ss) = Encaps(kem_pk)
           <----------------- ct --------------------------------

 ss = Decaps(kem_sk, ct)
 key = SHA256(ss)                                                     key = SHA256(ss)

           <==== ChaCha20-Poly1305(key, nonce_dir_counter, msg) ====>
```

Why it's structured this way:

- **ML-DSA-65 signs the ephemeral ML-KEM-768 key**, not the chat data
  itself. This is what prevents an active man-in-the-middle from
  swapping in their own KEM public key during the handshake — the
  client refuses to proceed unless the signature checks out against
  the server's known (pinned) identity key.
- **The KEM keypair is ephemeral** (fresh per connection). Only the
  ML-DSA-65 identity key is long-term. This gives you forward secrecy
  for the session key: compromising `kem_sk` after the session ends
  gets an attacker nothing, and even compromising the long-term
  `dsa_sk` later doesn't let them decrypt a session they didn't
  actively MITM at the time.
- **SHA-256(shared_secret)** turns the raw 32-byte ML-KEM-768 shared
  secret into the ChaCha20-Poly1305 key. This is intentionally simple
  for a demo; see "Hardening ideas" below for what a production
  build should use instead.
- **Direction-tagged nonces**: nonce = `4-byte direction id || 8-byte
  counter`. Server→client and client→server each keep their own
  monotonic counter, so the `(key, nonce)` pair is never reused even
  though both directions share one symmetric key — this is the one
  invariant ChaCha20-Poly1305 absolutely requires.

## Files

| File         | Purpose                                                        |
|--------------|-----------------------------------------------------------------|
| `common.h`   | Wire framing (`send_framed`/`recv_framed`), nonce/key derivation, ChaCha20-Poly1305 encrypt/decrypt via OpenSSL EVP |
| `server.c`   | Generates ML-DSA-65 identity key, runs the handshake as responder, chat loop |
| `client.c`   | Loads server's ML-DSA-65 public key, runs the handshake as initiator, chat loop |
| `Makefile`   | Builds both binaries                                            |

## Building liboqs

liboqs isn't packaged in standard apt repos, so build it from source
(this is exactly what was used to verify this demo):

```bash
git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git
cd liboqs
mkdir build && cd build

# Full build (all algorithms):
cmake -GNinja -DBUILD_SHARED_LIBS=ON ..

# OR faster: only the two algorithms this demo needs
cmake -GNinja -DBUILD_SHARED_LIBS=ON \
      -DOQS_MINIMAL_BUILD="KEM_ml_kem_768;SIG_ml_dsa_65" ..

ninja
sudo ninja install
sudo ldconfig
```

This installs headers to `/usr/local/include/oqs/` and
`liboqs.so`/`liboqs.a` to `/usr/local/lib/`. Confirmed algorithm ID
strings for this liboqs version: `OQS_KEM_alg_ml_kem_768` and
`OQS_SIG_alg_ml_dsa_65` (these are the FIPS 203 / FIPS 204 final
standard names — older liboqs releases used `Kyber768` /
`Dilithium3`-style names instead, so if you're on an older checkout
and get "undefined reference" errors, check
`OQS_KEM_alg_identifier()` / `oqs/kem.h` and `oqs/sig.h` for the exact
constants available in your build).

You'll also need OpenSSL dev headers for the AEAD:

```bash
sudo apt-get update && sudo apt-get install -y libssl-dev cmake ninja-build
```

## Building the demo

```bash
make
# or manually:
gcc -O2 -Wall -Wextra -std=c11 -o server server.c -loqs -lcrypto -lpthread
gcc -O2 -Wall -Wextra -std=c11 -o client client.c -loqs -lcrypto -lpthread
```

If liboqs was installed to `/usr/local` and your linker doesn't search
there by default, add `-I/usr/local/include -L/usr/local/lib` to both
commands, and make sure `/usr/local/lib` is in `LD_LIBRARY_PATH` (or
run `sudo ldconfig` after install).

## Running it

**Terminal 1 (server):**
```bash
./server 12345
```
This generates the server's ML-DSA-65 identity keypair and writes the
public half to `server_dsa_pub.key` in the current directory.

**Copy the trust anchor to the client's machine/directory:**
```bash
scp server_dsa_pub.key user@client-host:/path/to/client/
```
(For a same-machine test, `client` just needs `server_dsa_pub.key` in
its working directory — this is exactly what the verified test run
above did.)

**Terminal 2 (client):**
```bash
./client 127.0.0.1 12345
```

Type messages and press Enter on either side; `exit` on either side
closes the session.

Example verified session output:
```
[server] Sent signed ephemeral ML-KEM-768 public key (1184 B, sig 3309 B).
[server] Handshake complete - ML-KEM-768 shared secret established -> session key ready.

[client] Signature verified - ephemeral ML-KEM-768 key is authentic.
[client] Handshake complete - ML-KEM-768 shared secret established -> session key ready.
```
followed by messages typed on each side showing up decrypted on the
other (`[client] hello from client`, `[server] hello from server`).

## Sizes you'll actually see on the wire (from this liboqs build)

| Object                          | Size (bytes) |
|----------------------------------|--------------|
| ML-DSA-65 public key             | 1952         |
| ML-DSA-65 secret key             | 4032         |
| ML-DSA-65 signature              | 3309 (max)   |
| ML-KEM-768 public key            | 1184         |
| ML-KEM-768 secret key            | 2400         |
| ML-KEM-768 ciphertext            | 1088         |
| ML-KEM-768 shared secret         | 32           |
| ChaCha20-Poly1305 tag            | 16           |
| ChaCha20-Poly1305 nonce          | 12           |

## Known limitations of this demo (by design, for clarity)

- **Only the server authenticates itself.** The client is anonymous —
  there's no client-side ML-DSA-65 signature. For mutual auth, give
  the client its own long-term ML-DSA-65 keypair and have it sign the
  KEM ciphertext (or a transcript hash) before sending it back; the
  server then verifies against a pinned client public key.
- **Trust-on-first-use for the server's identity key.** `server_dsa_pub.key`
  is assumed to be delivered to the client over a trusted channel once.
  There's no PKI/CA here.
- **Single client at a time**, blocking sockets, one `accept()` — fine
  for a demo, not for a real service. For concurrent clients, fork a
  process or spawn a thread per `accept()`ed connection, each with its
  own ephemeral KEM keypair and session key.
- **No replay protection beyond the per-direction counter matching**
  in-order delivery. TCP guarantees ordering here, so this is fine for
  this transport, but note it would need a different design (e.g. a
  window) over lossy transports like UDP.
- **Key derivation is a plain SHA-256 of the shared secret.** Good
  enough to demonstrate the PQC primitives; a production system should
  use HKDF-SHA-384 (or -512) with a domain-separation label, and
  derive separate keys for each direction rather than reusing one key.

## Hardening ideas for a follow-on version

1. **Mutual authentication** — client signs its half of the handshake
   too (matches the pattern already used in your existing UDP-based
   4-way ML-KEM-768 + ML-DSA-65 handshake system).
2. **Hybrid classical+PQC KEM** — combine the ML-KEM-768 shared secret
   with an X25519 shared secret (concatenate-and-hash, or a proper
   hybrid KDF) so the scheme stays secure even if one primitive is
   later broken — matches the hybrid design in your
   `architecture_and_handshake.svg` work.
3. **Transcript binding** — instead of signing just `kem_pk`, sign a
   hash of the whole handshake transcript (both public keys +
   ciphertext) to close down transcript-substitution attacks.
4. **Rekeying** — rotate the session key after N messages or T seconds
   by running a fresh KEM exchange over the already-authenticated
   channel.
5. **AEAD associated data** — bind sequence numbers / connection IDs
   as AAD in `EVP_EncryptUpdate` (currently unused) to catch
   frame-reordering or splicing attempts at the framing layer.
