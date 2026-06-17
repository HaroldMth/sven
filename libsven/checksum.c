/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/checksum.c — Native SHA-256 file verification
 *
 * Self-contained SHA-256 (FIPS 180-4). Zero external deps —
 * works on any LFS system with just libc.
 *
 * Exported symbols:
 *   sven_sha256_file(path, hex_out, hex_out_sz)
 *       Compute the SHA-256 hex digest of a file.
 *       hex_out must be at least 65 bytes.
 *       Returns 0 on success, -1 on I/O error.
 *
 *   sven_verify_checksum(path, expected_hex)
 *       Returns  1 if the file's SHA-256 matches expected_hex (case-insensitive),
 *                0 if mismatch,
 *               -1 on I/O error or NULL input.
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>

/* ── SHA-256 constants ───────────────────────────────────────────────────── */

static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,
    0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
    0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,
    0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
    0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,
    0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
};

/* ── Bit operations ──────────────────────────────────────────────────────── */

#define ROTR32(x, n)  (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x,y,z)     (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)    (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)        (ROTR32(x,2)  ^ ROTR32(x,13) ^ ROTR32(x,22))
#define EP1(x)        (ROTR32(x,6)  ^ ROTR32(x,11) ^ ROTR32(x,25))
#define SIG0(x)       (ROTR32(x,7)  ^ ROTR32(x,18) ^ ((x) >> 3))
#define SIG1(x)       (ROTR32(x,17) ^ ROTR32(x,19) ^ ((x) >> 10))

/* ── SHA-256 context ─────────────────────────────────────────────────────── */

typedef struct {
    uint32_t state[8];
    uint64_t count;          /* total bits processed */
    uint8_t  buf[64];
    uint32_t buf_len;
} sha256_ctx;

static void sha256_init(sha256_ctx *ctx)
{
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    ctx->count   = 0;
    ctx->buf_len = 0;
}

static void sha256_transform(sha256_ctx *ctx, const uint8_t *block)
{
    uint32_t w[64], a, b, c, d, e, f, g, h, t1, t2;

    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i*4]     << 24)
             | ((uint32_t)block[i*4 + 1] << 16)
             | ((uint32_t)block[i*4 + 2] <<  8)
             |  (uint32_t)block[i*4 + 3];
    }
    for (int i = 16; i < 64; i++) {
        w[i] = SIG1(w[i-2]) + w[i-7] + SIG0(w[i-15]) + w[i-16];
    }

    a = ctx->state[0]; b = ctx->state[1];
    c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5];
    g = ctx->state[6]; h = ctx->state[7];

    for (int i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e,f,g) + K[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

static void sha256_update(sha256_ctx *ctx, const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        ctx->buf[ctx->buf_len++] = data[i];
        if (ctx->buf_len == 64) {
            sha256_transform(ctx, ctx->buf);
            ctx->buf_len = 0;
            ctx->count += 512;
        }
    }
}

static void sha256_final(sha256_ctx *ctx, uint8_t digest[32])
{
    uint64_t total_bits;
    uint32_t pad_len;

    ctx->count += (uint64_t)ctx->buf_len * 8;
    total_bits = ctx->count;

    /* Append 0x80 */
    ctx->buf[ctx->buf_len++] = 0x80;

    /* Pad to 56 bytes mod 64 */
    if (ctx->buf_len > 56) {
        while (ctx->buf_len < 64) ctx->buf[ctx->buf_len++] = 0;
        sha256_transform(ctx, ctx->buf);
        ctx->buf_len = 0;
    }
    while (ctx->buf_len < 56) ctx->buf[ctx->buf_len++] = 0;

    /* Append big-endian 64-bit bit count */
    for (int i = 7; i >= 0; i--) {
        ctx->buf[56 + (7 - i)] = (uint8_t)(total_bits >> (i * 8));
    }
    sha256_transform(ctx, ctx->buf);

    /* Write digest (big-endian) */
    for (int i = 0; i < 8; i++) {
        digest[i*4 + 0] = (uint8_t)(ctx->state[i] >> 24);
        digest[i*4 + 1] = (uint8_t)(ctx->state[i] >> 16);
        digest[i*4 + 2] = (uint8_t)(ctx->state[i] >>  8);
        digest[i*4 + 3] = (uint8_t)(ctx->state[i]      );
    }
}

/* ── Public API ──────────────────────────────────────────────────────────── */

#define READ_BUF_SIZE 65536

/*
 * sven_sha256_file — compute SHA-256 hex digest of a file.
 *
 * hex_out: caller-allocated buffer, must be >= 65 bytes.
 * Returns 0 on success, -1 on I/O error.
 */
int sven_sha256_file(const char *path, char *hex_out, size_t hex_out_sz)
{
    if (!path || !hex_out || hex_out_sz < 65) return -1;

    FILE *f = fopen(path, "rb");
    if (!f) return -1;

    sha256_ctx ctx;
    sha256_init(&ctx);

    static uint8_t buf[READ_BUF_SIZE];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) {
        sha256_update(&ctx, buf, n);
    }
    int err = ferror(f);
    fclose(f);
    if (err) return -1;

    uint8_t digest[32];
    sha256_final(&ctx, digest);

    /* Format as lowercase hex */
    static const char HEX[] = "0123456789abcdef";
    for (int i = 0; i < 32; i++) {
        hex_out[i*2 + 0] = HEX[digest[i] >> 4];
        hex_out[i*2 + 1] = HEX[digest[i] & 0x0f];
    }
    hex_out[64] = '\0';
    return 0;
}

/*
 * sven_verify_checksum — verify a file's SHA-256 against an expected hex string.
 *
 * Returns  1 — match
 *          0 — mismatch
 *         -1 — I/O error or bad args
 */
int sven_verify_checksum(const char *path, const char *expected_hex)
{
    if (!path || !expected_hex) return -1;
    if (strlen(expected_hex) != 64) return 0;   /* wrong length = definitely wrong */

    char actual[65];
    if (sven_sha256_file(path, actual, sizeof(actual)) != 0) return -1;

    /* Case-insensitive compare */
    for (int i = 0; i < 64; i++) {
        if (tolower((unsigned char)actual[i]) != tolower((unsigned char)expected_hex[i]))
            return 0;
    }
    return 1;
}
