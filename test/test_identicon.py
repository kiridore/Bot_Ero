"""core.gen_image.identicon：共享头像的确定性、几何布局与 PNG 输出。"""

from io import BytesIO
import unittest

from PIL import Image, ImageOps

from core.gen_image.identicon import generate_identicon


class IdenticonTest(unittest.TestCase):
    def test_deterministic_png_and_normalized_id(self):
        outputs = []
        for uid in (123456, "123456", "00123456"):
            image = generate_identicon(uid)
            self.assertEqual(image.size, (128, 128))
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.tobytes(), ImageOps.mirror(image).tobytes())
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            outputs.append(buffer.getvalue())
            with Image.open(BytesIO(outputs[-1])) as decoded:
                self.assertEqual(decoded.format, "PNG")
                self.assertEqual(decoded.tobytes(), image.tobytes())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_sample_users_have_different_patterns(self):
        images = [generate_identicon(uid) for uid in (123456, 654321, 987654)]
        self.assertEqual(len({im.tobytes() for im in images}), len(images))
        masks = [tuple(im.getpixel((x, y)) != (240, 240, 240)
                       for y in range(128) for x in range(128)) for im in images]
        self.assertEqual(len(set(masks)), len(images))

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            generate_identicon("../123")
