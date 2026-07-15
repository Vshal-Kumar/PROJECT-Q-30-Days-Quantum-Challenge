#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>

#include <oqs/oqs.h>
#include <openssl/evp.h>
#include <openssl/sha.h>

/* Direction tags keep the two peers' nonce spaces disjoint even though
 * both sides derive the SAME session key from the KEM shared secret. */
#define DIR_SERVER_TO_CLIENT 1u
#define DIR_CLIENT_TO_SERVER 2u

#define SESSION_KEY_LEN 32   /* ChaCha20-Poly1305 key size   */
#define NONCE_LEN       12   /* ChaCha20-Poly1305 nonce size */
#define TAG_LEN         16   /* Poly1305 tag size            */

static inline void die(const char *msg) {
    perror(msg);
    exit(EXIT_FAILURE);
}

/* ---------------------------------------------------------------------
 * Reliable send/recv over a blocking TCP socket
 * ------------------------------------------------------------------- */
static inline int send_all(int fd, const uint8_t *buf, size_t len) {
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = send(fd, buf + sent, len - sent, 0);
        if (n <= 0) return -1;
        sent += (size_t)n;
    }
    return 0;
}

static inline int recv_all(int fd, uint8_t *buf, size_t len) {
    size_t got = 0;
    while (got < len) {
        ssize_t n = recv(fd, buf + got, len - got, 0);
        if (n <= 0) return -1;
        got += (size_t)n;
    }
    return 0;
}

/* Length-prefixed framing: [4-byte big-endian length][payload]
 * Used for every message on the wire (handshake blobs AND chat messages),
 * so both peers always know exactly how many bytes to read next. */
static inline int send_framed(int fd, const uint8_t *buf, uint32_t len) {
    uint32_t netlen = htonl(len);
    if (send_all(fd, (uint8_t *)&netlen, 4) != 0) return -1;
    if (len > 0 && send_all(fd, buf, len) != 0) return -1;
    return 0;
}

/* Caller must free(*out_buf) when *out_len > 0 */
static inline int recv_framed(int fd, uint8_t **out_buf, uint32_t *out_len) {
    uint32_t netlen;
    if (recv_all(fd, (uint8_t *)&netlen, 4) != 0) return -1;
    uint32_t len = ntohl(netlen);
    if (len > (16u * 1024 * 1024)) return -1; /* sanity cap: 16MB */
    uint8_t *buf = NULL;
    if (len > 0) {
        buf = malloc(len);
        if (!buf) return -1;
        if (recv_all(fd, buf, len) != 0) { free(buf); return -1; }
    }
    *out_buf = buf;
    *out_len = len;
    return 0;
}

/* ---------------------------------------------------------------------
 * Key schedule: KEM shared secret -> symmetric session key
 * ------------------------------------------------------------------- */
static inline void derive_session_key(const uint8_t *shared_secret, size_t ss_len,
                                       uint8_t out_key[SESSION_KEY_LEN]) {
    /* SHA-256(shared_secret). In production, prefer a proper KDF
     * (e.g. HKDF-SHA384) with a context/label string bound in. */
    SHA256(shared_secret, ss_len, out_key);
}

/* 12-byte nonce = 4-byte direction id || 8-byte big-endian message counter.
 * Per-direction counters + the direction tag guarantee the (key, nonce)
 * pair is never reused, which is the hard requirement for ChaCha20-Poly1305. */
static inline void build_nonce(uint32_t direction, uint64_t counter, uint8_t nonce[NONCE_LEN]) {
    uint32_t dir_n = htonl(direction);
    memcpy(nonce, &dir_n, 4);
    for (int i = 0; i < 8; i++) {
        nonce[4 + i] = (uint8_t)(counter >> (56 - 8 * i));
    }
}

/* ---------------------------------------------------------------------
 * ChaCha20-Poly1305 AEAD (via OpenSSL EVP)
 * ------------------------------------------------------------------- */

/* out must have room for plen + TAG_LEN bytes. Returns ciphertext+tag
 * length, or -1 on error. */
static inline int aead_encrypt(const uint8_t key[SESSION_KEY_LEN],
                                const uint8_t nonce[NONCE_LEN],
                                const uint8_t *plaintext, int plen,
                                uint8_t *out) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, outlen = 0, ok = 0;
    if (!ctx) return -1;

    if (EVP_EncryptInit_ex(ctx, EVP_chacha20_poly1305(), NULL, NULL, NULL) != 1) goto done;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN, NONCE_LEN, NULL) != 1) goto done;
    if (EVP_EncryptInit_ex(ctx, NULL, NULL, key, nonce) != 1) goto done;

    if (EVP_EncryptUpdate(ctx, out, &len, plaintext, plen) != 1) goto done;
    outlen = len;
    if (EVP_EncryptFinal_ex(ctx, out + outlen, &len) != 1) goto done;
    outlen += len;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_GET_TAG, TAG_LEN, out + outlen) != 1) goto done;

    ok = 1;
done:
    EVP_CIPHER_CTX_free(ctx);
    return ok ? (outlen + TAG_LEN) : -1;
}

/* ciphertext is clen bytes, tag is the trailing TAG_LEN bytes.
 * out must have room for clen bytes. Returns plaintext length,
 * or -1 if authentication fails (message was tampered with / wrong key). */
static inline int aead_decrypt(const uint8_t key[SESSION_KEY_LEN],
                                const uint8_t nonce[NONCE_LEN],
                                const uint8_t *ciphertext, int clen,
                                const uint8_t tag[TAG_LEN],
                                uint8_t *out) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, outlen = 0, ok = 0;
    if (!ctx) return -1;

    if (EVP_DecryptInit_ex(ctx, EVP_chacha20_poly1305(), NULL, NULL, NULL) != 1) goto done;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN, NONCE_LEN, NULL) != 1) goto done;
    if (EVP_DecryptInit_ex(ctx, NULL, NULL, key, nonce) != 1) goto done;

    if (EVP_DecryptUpdate(ctx, out, &len, ciphertext, clen) != 1) goto done;
    outlen = len;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_TAG, TAG_LEN, (void *)tag) != 1) goto done;
    if (EVP_DecryptFinal_ex(ctx, out + outlen, &len) != 1) goto done; /* tag verified here */
    outlen += len;

    ok = 1;
done:
    EVP_CIPHER_CTX_free(ctx);
    return ok ? outlen : -1;
}

#endif /* COMMON_H */
