# LSB Steganography

Hide any file inside images, video, or audio using least-significant-bit steganography, with optional AES-256-GCM encryption and password-seeded position shuffling. Includes a desktop GUI, a CLI per stage, and analysis/visualization tools.

## Why this works

Every pixel channel / audio sample byte is 8 bits. Flipping the last bit changes the value by 1/255 (or 1/65536 for a 16-bit sample) — invisible to human perception, but a full data channel to a program. A "noise" cover (TV static, white noise) makes this even harder to detect statistically, since the carrier already looks like a random bitstream.

## Three pipelines, one payload format

| Carrier | Generator | Encoder / Decoder | GUI |
|---|---|---|---|
| Image (PNG) | `noise_image.py` | `lsb_encoder.py` / `lsb_decoder.py` | — (CLI only) |
| Video (lossless AVI) | `video_noise.py` | `video_encoder.py` / `video_decoder.py` | `app.py` |
| Audio (PCM WAV) | `audio_noise.py` | `audio_encoder.py` / `audio_decoder.py` | — (CLI only) |

Video and audio share a payload format (`payload.py`), an embedding helper (`embed.py`), and a position-shuffling scheme (`positions.py`) — the image pipeline uses `embed.py` too, but has no password/shuffling since it never carries encryption.

```
[LSTG][flag:1][...]
flag=0x00 (plain):              data_size:8 | name_len:2 | filename | data
flag=0x01 (encrypted, legacy):  cipher_size:8 | salt(16)+nonce(12)+AES-256-GCM(...)   — sequential order, decode-only
flag=0x02 (encrypted, current): cipher_size:8 | salt(16)+nonce(12)+AES-256-GCM(...)   — password-seeded shuffled order
```

Encryption (`crypto.py`) is PBKDF2-HMAC-SHA256 (600k iterations) → AES-256-GCM. A wrong password fails the GCM tag check outright rather than silently returning garbage.

## Two steganalysis defenses (this is the point of the tool)

**1. Position shuffling (`positions.py`, `crypto.derive_shuffle_seed`).** Without a password, the `LSTG` header sits at a fixed, scannable offset (frame 0 / sample 0) — anyone can grep any lossless carrier for it. With a password, both the header and the payload are written in a password-and-capacity-seeded shuffled order instead, so there is no fixed position to scan for. The shuffle seed is derived independently from the AES key (different KDF context), so the same key material is never reused for two purposes. To stay memory-bounded regardless of carrier size (a large video's pixel count can run into the hundreds of millions), the shuffle is two-level: block order (frame/sample-block) is permuted, and a single intra-block order is reused across blocks — O(blocks + block_size) memory instead of O(total capacity). Decoding tries the shuffled order first when a password is given, then falls back to sequential (covers plain files and the legacy 0x01 format).

**2. LSB matching, a.k.a. ±1 embedding (`embed.py`).** Straight bit replacement (`& 0xFE | bit`) always rounds a value to the nearest even/odd number matching the target bit, which skews the even/odd pixel-pair distribution in a way Chi-Square steganalysis specifically looks for. LSB matching only touches a value when its LSB doesn't already match the target bit, and then nudges it randomly ±1 (clamped at 0/255) instead of forcing a direction. Decoders are unaffected — they only ever read `value & 1`.

## Run it

```bash
pip install -r requirements.txt

# GUI (video pipeline) — hide/reveal panels, live capacity bar, password strength
python app.py

# Or step by step:
python demo.py          # image pipeline end-to-end
python video_demo.py    # video pipeline end-to-end
python audio_demo.py    # audio pipeline end-to-end (encrypted)
python player.py        # animated "static screen decoding a message" demo
```

Individual stages also work as CLIs, e.g.:

```bash
python lsb_encoder.py cover.png "secret" --output stego.png
python video_encoder.py noise.avi secret.zip --output stego.avi --password hunter2
python audio_encoder.py noise.wav secret.zip --output stego.wav --password hunter2
```

## Tests

Stdlib `unittest` (also pytest-discoverable, no extra dependency):

```bash
python -m unittest discover -s tests
```

Covers: AES-GCM round trip + wrong-password/corrupted-blob rejection, shuffle-seed determinism, LSB-matching round trip incl. 0/255 edge values, image/video/audio encode-decode round trips, capacity-exceeded errors, and a regression test proving the shuffled mode does **not** place `LSTG` at frame 0 / byte 0.

## Critical rules

| Rule | Why |
|---|---|
| PNG for images, lossless AVI (RGBA) for video, PCM WAV for audio | JPEG/H.264/MP4/MP3 compression destroys the LSB plane |
| Message/file length is embedded as a header | Decoder needs to know where to stop |
| Keep payload well under capacity | Smaller fill ratio = harder to detect statistically |

## Known limitation

Position shuffling only kicks in when a password is set — there's no secret to seed a permutation with otherwise, so unencrypted mode is a convenience format with no anti-scanning claim. The shuffle seed is deterministic per (password, capacity) pair; reusing the same password on two carriers of identical capacity produces the same visiting order (content still differs because of the random AES salt/nonce, but the *pattern* repeats). Not fixed, since doing so requires either storing extra random material in a fixed plaintext location (defeats the purpose) or accepting weaker discoverability guarantees — a real limitation of any scheme with no out-of-band channel, not an oversight.

## Roadmap ideas not yet done

- Format-preserving keyed permutation (Feistel-based) instead of the two-level block scheme, to remove the "same capacity → same pattern" edge case above — deliberately not built now: it's custom crypto-adjacent code for a marginal gain over the current scheme, not worth the review burden yet.
- GUI panels for the image and audio pipelines (currently CLI-only, `app.py` only wraps video).

## Reference

Petitcolas, Anderson, Kuhn (1999). *Information Hiding — A Survey*. Proceedings of the IEEE.
Westfeld & Pfitzmann (1999). *Attacks on Steganographic Systems*. ISSA.
