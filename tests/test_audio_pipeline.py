import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio_noise import generate_noise_wav
from audio_encoder import encode
from audio_decoder import decode

DURATION = 0.15  # saniye -> 44100*0.15*2 = 13230 ornek = 1653 byte kapasite


class TestAudioPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.noise_path = os.path.join(self.tmp.name, "noise.wav")
        self.stego_path = os.path.join(self.tmp.name, "stego.wav")
        self.secret_path = os.path.join(self.tmp.name, "secret.txt")
        self.recover_dir = os.path.join(self.tmp.name, "recovered")
        generate_noise_wav(self.noise_path, DURATION, seed=7)
        with open(self.secret_path, "w", encoding="utf-8") as f:
            f.write("ses icinde sir")

    def tearDown(self):
        self.tmp.cleanup()

    def test_plain_round_trip(self):
        encode(self.noise_path, self.secret_path, self.stego_path)
        path, was_enc = decode(self.stego_path, self.recover_dir)
        self.assertFalse(was_enc)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ses icinde sir")

    def test_encrypted_round_trip(self):
        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")
        path, was_enc = decode(self.stego_path, self.recover_dir, password="dogru-parola")
        self.assertTrue(was_enc)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ses icinde sir")

    def test_wrong_password_raises(self):
        encode(self.noise_path, self.secret_path, self.stego_path, password="dogru-parola")
        with self.assertRaises(ValueError):
            decode(self.stego_path, self.recover_dir, password="yanlis-parola")

    def test_capacity_exceeded_raises(self):
        big_path = os.path.join(self.tmp.name, "big.bin")
        with open(big_path, "wb") as f:
            f.write(os.urandom(3000))  # kapasitenin (1653 byte) uzerinde
        with self.assertRaises(ValueError):
            encode(self.noise_path, big_path, self.stego_path)


if __name__ == "__main__":
    unittest.main()
