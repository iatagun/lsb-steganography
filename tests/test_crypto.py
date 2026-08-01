import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crypto


class TestCrypto(unittest.TestCase):
    def test_encrypt_decrypt_round_trip(self):
        data = b"gizli veri \x00\x01\xff bitmis"
        blob = crypto.encrypt(data, "dogru-parola")
        self.assertEqual(crypto.decrypt(blob, "dogru-parola"), data)

    def test_wrong_password_raises(self):
        blob = crypto.encrypt(b"veri", "dogru-parola")
        with self.assertRaises(ValueError):
            crypto.decrypt(blob, "yanlis-parola")

    def test_corrupted_blob_raises(self):
        blob = crypto.encrypt(b"veri", "parola")
        corrupted = blob[:-1] + bytes([blob[-1] ^ 0xFF])
        with self.assertRaises(ValueError):
            crypto.decrypt(corrupted, "parola")

    def test_too_short_blob_raises(self):
        with self.assertRaises(ValueError):
            crypto.decrypt(b"kisa", "parola")

    def test_shuffle_seed_deterministic(self):
        s1 = crypto.derive_shuffle_seed("parola", 10_000)
        s2 = crypto.derive_shuffle_seed("parola", 10_000)
        self.assertEqual(s1, s2)

    def test_shuffle_seed_varies_with_capacity(self):
        s1 = crypto.derive_shuffle_seed("parola", 10_000)
        s2 = crypto.derive_shuffle_seed("parola", 20_000)
        self.assertNotEqual(s1, s2)

    def test_shuffle_seed_varies_with_password(self):
        s1 = crypto.derive_shuffle_seed("parola-a", 10_000)
        s2 = crypto.derive_shuffle_seed("parola-b", 10_000)
        self.assertNotEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
