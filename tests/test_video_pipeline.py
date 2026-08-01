import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video_noise import generate_noise_video
from video_encoder import encode
from video_decoder import decode

W, H, FPS, DUR = 16, 16, 5, 2.0   # -> 10 kare, 16*16*3*10 = 7680 bit = 960 byte kapasite


class TestVideoPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.noise_path = os.path.join(self.tmp.name, "noise.avi")
        self.stego_path = os.path.join(self.tmp.name, "stego.avi")
        self.secret_path = os.path.join(self.tmp.name, "secret.txt")
        self.recover_dir = os.path.join(self.tmp.name, "recovered")
        generate_noise_video(self.noise_path, W, H, FPS, DUR, seed=7)
        with open(self.secret_path, "w", encoding="utf-8") as f:
            f.write("kucuk bir sir")

    def tearDown(self):
        self.tmp.cleanup()

    def test_plain_round_trip(self):
        encode(self.noise_path, self.secret_path, self.stego_path)
        path, was_enc = decode(self.stego_path, self.recover_dir)
        self.assertFalse(was_enc)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "kucuk bir sir")

    def test_encrypted_round_trip(self):
        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")
        path, was_enc = decode(self.stego_path, self.recover_dir, password="dogru-parola")
        self.assertTrue(was_enc)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "kucuk bir sir")

    def test_wrong_password_raises(self):
        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")
        with self.assertRaises(ValueError):
            decode(self.stego_path, self.recover_dir, password="yanlis-parola")

    def test_missing_password_raises(self):
        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")
        with self.assertRaises(ValueError):
            decode(self.stego_path, self.recover_dir)

    def test_capacity_exceeded_raises(self):
        big_path = os.path.join(self.tmp.name, "big.bin")
        with open(big_path, "wb") as f:
            f.write(os.urandom(2000))  # kapasitenin (960 byte) uzerinde
        with self.assertRaises(ValueError):
            encode(self.noise_path, big_path, self.stego_path)

    def test_shuffled_header_not_at_fixed_position(self):
        """Parolali gomme, MAGIC'i kare-0'in ilk baytlarina sabitlemez."""
        import numpy as np
        import cv2

        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")

        cap = cv2.VideoCapture(self.stego_path)
        ret, frame0 = cap.read()
        cap.release()
        self.assertTrue(ret)

        flat = frame0.flatten()
        header_bits = [int(flat[i] & 1) for i in range(40)]
        header_bytes = bytes(
            sum(b << (7 - j) for j, b in enumerate(header_bits[i:i + 8]))
            for i in range(0, 40, 8)
        )
        self.assertNotEqual(header_bytes[:4], b"LSTG")


if __name__ == "__main__":
    unittest.main()
