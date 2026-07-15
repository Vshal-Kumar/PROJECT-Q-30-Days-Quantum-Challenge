/* server.c
 *
 * PQC secure-chat SERVER demo.
 *
 * Handshake:
 *   1. Server has (or generates) a long-term ML-DSA-65 identity keypair.
 *      Its public key is written to disk so it can be distributed to
 *      clients out-of-band (this is the "trust anchor" for the demo,
 *      analogous to a pinned certificate).
 *   2. On each connection the server generates a FRESH (ephemeral)
 *      ML-KEM-768 keypair and sends: kem_pk || Sign(dsa_sk, kem_pk).
 *   3. Client verifies the signature against the known dsa_pk, then
 *      encapsulates against kem_pk and sends back the KEM ciphertext.
 *   4. Server decapsulates -> both sides now hold the same 32-byte
 *      ML-KEM-768 shared secret -> SHA-256 -> ChaCha20-Poly1305 session key.
 *   5. Chat proceeds as length-prefixed, individually AEAD-encrypted
 *      frames in both directions.
 */
#include "common.h"
#include <netinet/in.h>
#include <sys/select.h>

#define DSA_PUBKEY_FILE "server_dsa_pub.key"

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <listen-port>\n", argv[0]);
        return 1;
    }
    int port = atoi(argv[1]);

    /* ---- 1. Long-term ML-DSA-65 identity keypair ---- */
    OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65);
    if (!sig) die("OQS_SIG_new(ML-DSA-65) failed - check liboqs build config");

    uint8_t *dsa_pk = malloc(sig->length_public_key);
    uint8_t *dsa_sk = malloc(sig->length_secret_key);
    if (!dsa_pk || !dsa_sk) die("malloc");

    if (OQS_SIG_keypair(sig, dsa_pk, dsa_sk) != OQS_SUCCESS) die("OQS_SIG_keypair failed");

    FILE *f = fopen(DSA_PUBKEY_FILE, "wb");
    if (!f) die("fopen dsa pubkey file");
    fwrite(dsa_pk, 1, sig->length_public_key, f);
    fclose(f);
    printf("[server] Generated ML-DSA-65 identity keypair (pk=%zu B, sk=%zu B).\n",
           sig->length_public_key, sig->length_secret_key);
    printf("[server] Public key written to '%s' -> copy this file next to the client binary.\n",
           DSA_PUBKEY_FILE);

    /* ---- 2. TCP listen ---- */
    int listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd < 0) die("socket");
    int opt = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons((uint16_t)port);

    if (bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) die("bind");
    if (listen(listen_fd, 1) < 0) die("listen");
    printf("[server] Listening on 0.0.0.0:%d ...\n", port);

    struct sockaddr_in client_addr;
    socklen_t client_len = sizeof(client_addr);
    int conn_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
    if (conn_fd < 0) die("accept");
    printf("[server] Client connected: %s:%d\n",
           inet_ntoa(client_addr.sin_addr), ntohs(client_addr.sin_port));

    /* ---- 3. Ephemeral ML-KEM-768 keypair for THIS session ---- */
    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) die("OQS_KEM_new(ML-KEM-768) failed - check liboqs build config");

    uint8_t *kem_pk = malloc(kem->length_public_key);
    uint8_t *kem_sk = malloc(kem->length_secret_key);
    if (!kem_pk || !kem_sk) die("malloc");

    if (OQS_KEM_keypair(kem, kem_pk, kem_sk) != OQS_SUCCESS) die("OQS_KEM_keypair failed");

    uint8_t *signature = malloc(sig->length_signature);
    size_t sig_len = 0;
    if (OQS_SIG_sign(sig, signature, &sig_len, kem_pk, kem->length_public_key, dsa_sk) != OQS_SUCCESS)
        die("OQS_SIG_sign failed");

    if (send_framed(conn_fd, kem_pk, (uint32_t)kem->length_public_key) != 0) die("send kem_pk");
    if (send_framed(conn_fd, signature, (uint32_t)sig_len) != 0) die("send signature");
    printf("[server] Sent signed ephemeral ML-KEM-768 public key (%zu B, sig %zu B).\n",
           kem->length_public_key, sig_len);

    /* ---- 4. Receive KEM ciphertext, decapsulate ---- */
    uint8_t *ct = NULL;
    uint32_t ct_len = 0;
    if (recv_framed(conn_fd, &ct, &ct_len) != 0 || ct_len != kem->length_ciphertext)
        die("recv kem ciphertext (wrong size or connection dropped)");

    uint8_t shared_secret[64];
    if (kem->length_shared_secret > sizeof(shared_secret)) die("shared secret too large");
    if (OQS_KEM_decaps(kem, shared_secret, ct, kem_sk) != OQS_SUCCESS) die("OQS_KEM_decaps failed");
    free(ct);

    uint8_t session_key[SESSION_KEY_LEN];
    derive_session_key(shared_secret, kem->length_shared_secret, session_key);
    OQS_MEM_cleanse(shared_secret, sizeof(shared_secret));
    printf("[server] Handshake complete - ML-KEM-768 shared secret established -> session key ready.\n");
    printf("[server] Type a message and press Enter to send. Type 'exit' to quit.\n\n> ");
    fflush(stdout);

    /* ---- 5. Encrypted chat loop ---- */
    uint64_t send_ctr = 0, recv_ctr = 0;
    char line[4096];

    for (;;) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(STDIN_FILENO, &rfds);
        FD_SET(conn_fd, &rfds);
        int maxfd = conn_fd > STDIN_FILENO ? conn_fd : STDIN_FILENO;

        if (select(maxfd + 1, &rfds, NULL, NULL, NULL) < 0) die("select");

        if (FD_ISSET(conn_fd, &rfds)) {
            uint8_t *ct_msg = NULL;
            uint32_t ct_msg_len = 0;
            if (recv_framed(conn_fd, &ct_msg, &ct_msg_len) != 0) {
                printf("\n[server] Client disconnected.\n");
                break;
            }
            if (ct_msg_len < TAG_LEN) { free(ct_msg); continue; }
            int plen = (int)ct_msg_len - TAG_LEN;
            uint8_t *pt = malloc((size_t)plen + 1);
            uint8_t nonce[NONCE_LEN];
            build_nonce(DIR_CLIENT_TO_SERVER, recv_ctr, nonce);

            int rc = aead_decrypt(session_key, nonce, ct_msg, plen, ct_msg + plen, pt);
            free(ct_msg);
            if (rc < 0) {
                printf("\n[server] !! AEAD authentication failed on incoming message - dropped !!\n> ");
                fflush(stdout);
                free(pt);
                continue;
            }
            recv_ctr++;
            pt[rc] = '\0';
            printf("\r[client] %s\n> ", pt);
            fflush(stdout);
            free(pt);
        }

        if (FD_ISSET(STDIN_FILENO, &rfds)) {
            if (!fgets(line, sizeof(line), stdin)) {
                printf("\n[server] EOF on stdin, closing.\n");
                break;
            }
            line[strcspn(line, "\n")] = '\0';
            if (strcmp(line, "exit") == 0) break;
            if (strlen(line) == 0) { printf("> "); fflush(stdout); continue; }

            int plen = (int)strlen(line);
            uint8_t *out = malloc((size_t)plen + TAG_LEN);
            uint8_t nonce[NONCE_LEN];
            build_nonce(DIR_SERVER_TO_CLIENT, send_ctr, nonce);

            int outlen = aead_encrypt(session_key, nonce, (uint8_t *)line, plen, out);
            if (outlen < 0) { fprintf(stderr, "encrypt failed\n"); free(out); continue; }
            send_ctr++;

            if (send_framed(conn_fd, out, (uint32_t)outlen) != 0) {
                free(out);
                printf("[server] send failed, client appears gone.\n");
                break;
            }
            free(out);
            printf("> ");
            fflush(stdout);
        }
    }

    close(conn_fd);
    close(listen_fd);
    OQS_MEM_secure_free(kem_sk, kem->length_secret_key);
    OQS_MEM_secure_free(dsa_sk, sig->length_secret_key);
    OQS_MEM_cleanse(session_key, sizeof(session_key));
    free(kem_pk); free(signature); free(dsa_pk);
    OQS_KEM_free(kem);
    OQS_SIG_free(sig);
    return 0;
}
