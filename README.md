# LSB Steganography

Hide any file inside images or video using least-significant-bit steganography, with optional AES-256-GCM encryption. Includes a desktop GUI, a CLI per stage, and analysis/visualization tools.

## Why this works

Every pixel channel is 8 bits. Flipping the last bit changes a color value by 1/255 — invisible to the human eye, but a full data channel to a program. A "noise" cover (TV static-style random pixels) makes this even harder to detect statistically, since the carrier already looks like a random bitstream.

## Two pipelines

**Image** (`noise_image.py` → `lsb_encoder.py` / `lsb_decoder.py` → `lsb_visualizer.py`)
Embeds UTF-8 text in a PNG. `lsb_visualizer.py` renders the cover, the stego image, an amplified diff map, and the raw LSB bit-plane, plus PSNR.

**Video** (`video_noise.py` → `video_encoder.py` / `video_decoder.py`)
Embeds an arbitrary file (name + bytes) across the LSBs of a lossless AVI (RGBA fourcc) noise video. Payload format:

```
[LSTG][flag:1][...]
flag=0x00 (plain):     data_size:8 | name_len:2 | filename | data
flag=0x01 (encrypted):  cipher_size:8 | salt(16)+nonce(12)+AES-256-GCM(data_size+name_len+filename+data)
```

Encryption (`crypto.py`) is PBKDF2-HMAC-SHA256 (600k iterations) → AES-256-GCM. A wrong password fails the GCM tag check outright rather than silently returning garbage.

## Run it

```bash
pip install -r requirements.txt

# GUI (recommended) — hide/reveal panels, live capacity bar, password strength
python app.py

# Or step by step:
python demo.py          # image pipeline end-to-end
python video_demo.py    # video pipeline end-to-end
python player.py        # animated "static screen decoding a message" demo
```

Individual stages also work as CLIs, e.g. `python lsb_encoder.py cover.png "secret" --output stego.png` or `python video_encoder.py noise.avi secret.zip --output stego.avi --password hunter2`.

## Critical rules

| Rule | Why |
|---|---|
| PNG for images, lossless AVI (RGBA) for video | JPEG/H.264/MP4 compression destroys the LSB plane |
| Message/file length is embedded as a header | Decoder needs to know where to stop |
| Keep payload well under capacity | Smaller fill ratio = harder to detect statistically |

## Known limitation

The `LSTG` magic bytes and header are always at a fixed, deterministic position (frame 0, first pixels) — even when the payload itself is encrypted. A scanner that checks the first few LSBs of any lossless video/image for that signature can flag it as "likely stego" without breaking the encryption. Randomizing the embedding order (password-seeded PRNG over pixel/frame positions) would close this gap — see Roadmap.

## Roadmap ideas

- Password-seeded pixel/frame shuffling so there's no fixed, scannable header position (currently the weak point above).
- LSB matching (±1 randomly) instead of straight bit replacement — resists chi-square steganalysis better.
- Audio (WAV) carrier as a third pipeline, reusing the same payload format.
- `pytest` coverage for encode/decode round-trips and the crypto module (currently only manual demo scripts).

## Reference

Petitcolas, Anderson, Kuhn (1999). *Information Hiding — A Survey*. Proceedings of the IEEE.
Westfeld & Pfitzmann (1999). *Attacks on Steganographic Systems*. ISSA.
