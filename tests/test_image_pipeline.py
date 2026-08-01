import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noise_image import generate_noise_image
from lsb_encoder import encode
from lsb_decoder import decode


class TestImagePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cover = os.path.join(self.tmp.name, "noise.png")
        self.stego = os.path.join(self.tmp.name, "stego.png")
        generate_noise_image(64, 64, seed=7).save(self.cover)

    def tearDown(self):
        self.tmp.cleanup()

    def test_short_message_round_trip(self):
        msg = "Merhaba dunya! 123"
        encode(self.cover, msg, self.stego)
        self.assertEqual(decode(self.stego), msg)

    def test_message_near_capacity_round_trip(self):
        capacity = (64 * 64 * 3) // 8 - 4
        msg = "x" * (capacity - 5)
        encode(self.cover, msg, self.stego)
        self.assertEqual(decode(self.stego), msg)

    def test_capacity_exceeded_raises(self):
        capacity = (64 * 64 * 3) // 8
        msg = "x" * (capacity + 100)
        with self.assertRaises(ValueError):
            encode(self.cover, msg, self.stego)

    def test_decode_without_embedded_message_is_garbage_or_error(self):
        # Rastgele gürültüde header uzunluğu neredeyse hep gecersiz olur.
        try:
            decode(self.cover)
        except (ValueError, UnicodeDecodeError):
            pass  # beklenen davranislardan biri


if __name__ == "__main__":
    unittest.main()
