/* client.c
 *
 * PQC secure-chat CLIENT demo. See server.c for the full handshake
 * description. The client's job:
 *   1. Load the server's long-term ML-DSA-65 public key from disk
 *      (must be copied from the server beforehand - this is the
 *      trust anchor / TOFU pin for this demo).
 *   2. Connect, receive (kem_pk, signature), verify the signature.
 *      If verification fails, ABORT - this is exactly the check that
 *      stops a man-in-the-middle from substituting their own KEM key.
 *   3. Encapsulate against kem_pk -> get (ciphertext, shared_secret),
 *      send ciphertext back to the server.
 *   4. Derive the same session key the server derived, then chat.
 */
#include "common.h"
#include <netinet/in.h>
#include <sys/select.h>

#define DSA_PUBKEY_FILE "server_dsa_pub.key"

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <server-ip> <server-port>\n", argv[0]);
        return 1;
    }
    const char *server_ip = argv[1];
    int port = atoi(argv[2]);

    /* ---- 1. Load server's long-term ML-DSA-65 public key ---- */
    OQS_SIG *sig = OQS_SIG_new(OQS_SIG_alg_ml_dsa_65);
    if (!sig) die("OQS_SIG_new(ML-DSA-65) failed - check liboqs build config");

    uint8_t *dsa_pk = malloc(sig->length_public_key);
    if (!dsa_pk) die("malloc");

    FILE *f = fopen(DSA_PUBKEY_FILE, "rb");
    if (!f) die("fopen server_dsa_pub.key - copy it from the server first");
    size_t rd = fread(dsa_pk, 1, sig->length_public_key, f);
    fclose(f);
    if (rd != sig->length_public_key) die("server_dsa_pub.key has the wrong size/content");
    printf("[client] Loaded server's ML-DSA-65 public key (%zu B).\n", sig->length_public_key);

    /* ---- 2. Connect ---- */
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) die("socket");

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, server_ip, &addr.sin_addr) != 1) die("inet_pton: bad server IP");

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) die("connect");
    printf("[client] Connected to %s:%d\n", server_ip, port);

    OQS_KEM *kem = OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
    if (!kem) die("OQS_KEM_new(ML-KEM-768) failed - check liboqs build config");

    uint8_t *kem_pk = NULL, *signature = NULL;
    uint32_t kem_pk_len = 0, sig_len = 0;
    if (recv_framed(fd, &kem_pk, &kem_pk_len) != 0) die("recv kem_pk");
    if (recv_framed(fd, &signature, &sig_len) != 0) die("recv signature");

    if (kem_pk_len != kem->length_public_key) {
        fprintf(stderr, "[client] Unexpected KEM public key size (%u != %zu)\n",
                kem_pk_len, kem->length_public_key);
        exit(EXIT_FAILURE);
    }

    /* ---- THE critical authentication check ---- */
    OQS_STATUS verify_rc = OQS_SIG_verify(sig, kem_pk, kem_pk_len, signature, sig_len, dsa_pk);
    if (verify_rc != OQS_SUCCESS) {
        fprintf(stderr, "[client] !! ML-DSA-65 signature verification FAILED !!\n");
        fprintf(stderr, "[client] The ephemeral key did not come from the holder of the pinned\n");
        fprintf(stderr, "[client] identity key - refusing to proceed (possible MITM). Aborting.\n");
        exit(EXIT_FAILURE);
    }
    printf("[client] Signature verified - ephemeral ML-KEM-768 key is authentic.\n");

    /* ---- 3. Encapsulate ---- */
    uint8_t *ct = malloc(kem->length_ciphertext);
    uint8_t shared_secret[64];
    if (kem->length_shared_secret > sizeof(shared_secret)) die("shared secret too large");

    if (OQS_KEM_encaps(kem, ct, shared_secret, kem_pk) != OQS_SUCCESS) die("OQS_KEM_encaps failed");
    if (send_framed(fd, ct, (uint32_t)kem->length_ciphertext) != 0) die("send ciphertext");

    uint8_t session_key[SESSION_KEY_LEN];
    derive_session_key(shared_secret, kem->length_shared_secret, session_key);
    OQS_MEM_cleanse(shared_secret, sizeof(shared_secret));
    printf("[client] Handshake complete - ML-KEM-768 shared secret established -> session key ready.\n");
    printf("[client] Type a message and press Enter to send. Type 'exit' to quit.\n\n> ");
    fflush(stdout);

    /* ---- 4. Encrypted chat loop (mirror of server.c, directions swapped) ---- */
    uint64_t send_ctr = 0, recv_ctr = 0;
    char line[4096];

    for (;;) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(STDIN_FILENO, &rfds);
        FD_SET(fd, &rfds);
        int maxfd = fd > STDIN_FILENO ? fd : STDIN_FILENO;

        if (select(maxfd + 1, &rfds, NULL, NULL, NULL) < 0) die("select");

        if (FD_ISSET(fd, &rfds)) {
            uint8_t *ct_msg = NULL;
            uint32_t ct_msg_len = 0;
            if (recv_framed(fd, &ct_msg, &ct_msg_len) != 0) {
                printf("\n[client] Server disconnected.\n");
                break;
            }
            if (ct_msg_len < TAG_LEN) { free(ct_msg); continue; }
            int plen = (int)ct_msg_len - TAG_LEN;
            uint8_t *pt = malloc((size_t)plen + 1);
            uint8_t nonce[NONCE_LEN];
            build_nonce(DIR_SERVER_TO_CLIENT, recv_ctr, nonce);

            int rc = aead_decrypt(session_key, nonce, ct_msg, plen, ct_msg + plen, pt);
            free(ct_msg);
            if (rc < 0) {
                printf("\n[client] !! AEAD authentication failed on incoming message - dropped !!\n> ");
                fflush(stdout);
                free(pt);
                continue;
            }
            recv_ctr++;
            pt[rc] = '\0';
            printf("\r[server] %s\n> ", pt);
            fflush(stdout);
            free(pt);
        }

        if (FD_ISSET(STDIN_FILENO, &rfds)) {
            if (!fgets(line, sizeof(line), stdin)) {
                printf("\n[client] EOF on stdin, closing.\n");
                break;
            }
            line[strcspn(line, "\n")] = '\0';
            if (strcmp(line, "exit") == 0) break;
            if (strlen(line) == 0) { printf("> "); fflush(stdout); continue; }

            int plen = (int)strlen(line);
            uint8_t *out = malloc((size_t)plen + TAG_LEN);
            uint8_t nonce[NONCE_LEN];
            build_nonce(DIR_CLIENT_TO_SERVER, send_ctr, nonce);

            int outlen = aead_encrypt(session_key, nonce, (uint8_t *)line, plen, out);
            if (outlen < 0) { fprintf(stderr, "encrypt failed\n"); free(out); continue; }
            send_ctr++;

            if (send_framed(fd, out, (uint32_t)outlen) != 0) {
                free(out);
                printf("[client] send failed, server appears gone.\n");
                break;
            }
            free(out);
            printf("> ");
            fflush(stdout);
        }
    }

    close(fd);
    free(kem_pk); free(signature); free(ct); free(dsa_pk);
    OQS_MEM_cleanse(session_key, sizeof(session_key));
    OQS_KEM_free(kem);
    OQS_SIG_free(sig);
    return 0;
}
