# test_v250_engine.py — Unit & Integration Test Suite for FXbatch v2.5.0
import io
import os
import shutil
import tempfile
import unittest
from PIL import Image

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from image_compressor import (
    compute_target_dimensions,
    _crop_to_square,
    _prepare_image_for_format,
    build_output_filename,
    compress_and_resize_image,
    encode_sample_in_memory,
    process_images_in_folder,
)


class TestFXbatchV250Engine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fxbatch_test_")
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # Create sample test images
        # 1. 16:9 Landscape RGB image
        self.img_16_9 = os.path.join(self.input_dir, "photo_landscape.jpg")
        img = Image.new("RGB", (1920, 1080), (100, 150, 200))
        img.save(self.img_16_9, format="JPEG", quality=90)

        # 2. 1:1 Square RGBA image (with transparent circle)
        self.img_square_rgba = os.path.join(self.input_dir, "logo_transparent.png")
        rgba = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(rgba)
        draw.ellipse((50, 50, 450, 450), fill=(255, 50, 50, 200))
        rgba.save(self.img_square_rgba, format="PNG")

        # 3. Grayscale LA image (grayscale + alpha channel)
        self.img_la = os.path.join(self.input_dir, "grayscale_alpha.png")
        la = Image.new("LA", (300, 300), (128, 180))
        la.save(self.img_la, format="PNG")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 1. Sizing Mode Dimension Calculations
    # ------------------------------------------------------------------
    def test_sizing_percentage(self):
        w, h = compute_target_dimensions(1000, 800, "percent", {"percent": 50})
        self.assertEqual((w, h), (500, 400))

        # Test upscaling
        w2, h2 = compute_target_dimensions(200, 100, "percent", {"percent": 150})
        self.assertEqual((w2, h2), (300, 150))

    def test_sizing_bounding_box(self):
        # 4000x2000 (2:1) fitting inside 1920x1080 -> limited by width: 1920x960
        w, h = compute_target_dimensions(4000, 2000, "bounding_box", {"max_width": 1920, "max_height": 1080})
        self.assertEqual((w, h), (1920, 960))

        # 2000x4000 (1:2) fitting inside 1920x1080 -> limited by height: 540x1080
        w2, h2 = compute_target_dimensions(2000, 4000, "bounding_box", {"max_width": 1920, "max_height": 1080})
        self.assertEqual((w2, h2), (540, 1080))

    def test_sizing_fixed_width_and_height(self):
        # Fixed width
        w, h = compute_target_dimensions(1000, 500, "fixed_width", {"fixed_width": 1200})
        self.assertEqual((w, h), (1200, 600))

        # Fixed height
        w2, h2 = compute_target_dimensions(1000, 500, "fixed_height", {"fixed_height": 250})
        self.assertEqual((w2, h2), (500, 250))

    def test_sizing_ico(self):
        w, h = compute_target_dimensions(1920, 1080, "ico", {"ico_size": "bundle"})
        self.assertEqual((w, h), (256, 256))

        w2, h2 = compute_target_dimensions(1920, 1080, "ico", {"ico_size": "48"})
        self.assertEqual((w2, h2), (48, 48))

    # ------------------------------------------------------------------
    # 2. Square Cropping for ICO Format
    # ------------------------------------------------------------------
    def test_crop_to_square(self):
        img_landscape = Image.new("RGB", (1920, 1080))
        cropped = _crop_to_square(img_landscape)
        self.assertEqual(cropped.size, (1080, 1080))

        img_portrait = Image.new("RGB", (800, 1200))
        cropped_portrait = _crop_to_square(img_portrait)
        self.assertEqual(cropped_portrait.size, (800, 800))

        img_square = Image.new("RGB", (512, 512))
        self.assertEqual(_crop_to_square(img_square).size, (512, 512))

    # ------------------------------------------------------------------
    # 3. WebP LA Mode Alpha Preservation (Bug Fix Verification)
    # ------------------------------------------------------------------
    def test_webp_la_alpha_preservation(self):
        la_img = Image.new("LA", (100, 100), (200, 128))
        prep = _prepare_image_for_format(la_img, "webp")
        self.assertEqual(prep.mode, "RGBA")
        # Check that alpha channel has non-zero transparency
        alpha = prep.split()[3]
        self.assertEqual(alpha.getpixel((50, 50)), 128)

    # ------------------------------------------------------------------
    # 4. Naming Tokens Replacement
    # ------------------------------------------------------------------
    def test_naming_tokens(self):
        rendered = build_output_filename("photo.jpg", "png", "{name}_{w}x{h}_q{quality}", new_w=800, new_h=600, quality=75)
        self.assertEqual(rendered, "photo_800x600_q75.png")

        # Fallback when {name} missing
        fallback = build_output_filename("icon.png", "ico", "no_token_here")
        self.assertEqual(fallback, "icon.ico")

    # ------------------------------------------------------------------
    # 5. Conversion to ICO Format
    # ------------------------------------------------------------------
    def test_ico_bundle_conversion(self):
        out_ico = os.path.join(self.output_dir, "test_logo.ico")
        args = (
            self.img_square_rgba,
            out_ico,
            60,
            "ico",
            {"ico_size": "bundle"},
            (72, 72),
            "ico",
            "lanczos",
            False,
        )
        res = compress_and_resize_image(args)
        self.assertEqual(res.status, "ok")
        self.assertTrue(os.path.exists(out_ico))
        self.assertGreater(res.output_bytes, 0)

        # Verify multi-size bundle
        with Image.open(out_ico) as ico:
            self.assertEqual(ico.format, "ICO")
            sizes = getattr(ico, "info", {}).get("sizes", set())
            self.assertIn((16, 16), sizes)
            self.assertIn((32, 32), sizes)
            self.assertIn((48, 48), sizes)
            self.assertIn((256, 256), sizes)

    def test_ico_from_non_square_auto_cropped(self):
        out_ico = os.path.join(self.output_dir, "from_landscape.ico")
        args = (
            self.img_16_9,
            out_ico,
            60,
            "ico",
            {"ico_size": "64"},
            (72, 72),
            "ico",
            "lanczos",
            False,
        )
        res = compress_and_resize_image(args)
        self.assertEqual(res.status, "ok")
        with Image.open(out_ico) as ico:
            self.assertEqual(ico.size, (64, 64))

    # ------------------------------------------------------------------
    # 6. Conversion to AVIF Format
    # ------------------------------------------------------------------
    def test_avif_conversion(self):
        out_avif = os.path.join(self.output_dir, "photo.avif")
        args = (
            self.img_16_9,
            out_avif,
            50,
            "percent",
            {"percent": 50},
            (72, 72),
            "avif",
            "lanczos",
            False,
        )
        res = compress_and_resize_image(args)
        self.assertEqual(res.status, "ok")
        self.assertTrue(os.path.exists(out_avif))
        with Image.open(out_avif) as avif_img:
            self.assertEqual(avif_img.format, "AVIF")
            self.assertEqual(avif_img.size, (960, 540))

    # ------------------------------------------------------------------
    # 7. Collision Policies (Overwrite, Rename, Skip)
    # ------------------------------------------------------------------
    def test_batch_collision_policies(self):
        # 1. First run: Overwrite (default)
        res1 = process_images_in_folder(
            self.input_dir,
            self.output_dir,
            quality=70,
            resize_mode="percent",
            resize_params={"percent": 50},
            dpi=72,
            progress_callback=None,
            cancel_event=None,
            image_type="jpg",
            collision_policy="overwrite",
        )
        self.assertEqual(len([r for r in res1 if r.status == "ok"]), 3)

        # 2. Second run with policy 'skip': all existing should be skipped
        res_skip = process_images_in_folder(
            self.input_dir,
            self.output_dir,
            quality=70,
            resize_mode="percent",
            resize_params={"percent": 50},
            dpi=72,
            progress_callback=None,
            cancel_event=None,
            image_type="jpg",
            collision_policy="skip",
        )
        skipped = [r for r in res_skip if r.status == "skipped"]
        self.assertEqual(len(skipped), 3)

        # 3. Third run with policy 'rename': should create _1 duplicates
        res_rename = process_images_in_folder(
            self.input_dir,
            self.output_dir,
            quality=70,
            resize_mode="percent",
            resize_params={"percent": 50},
            dpi=72,
            progress_callback=None,
            cancel_event=None,
            image_type="jpg",
            collision_policy="rename",
        )
        ok_rename = [r for r in res_rename if r.status == "ok"]
        self.assertEqual(len(ok_rename), 3)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, "photo_landscape_1.jpg")))


if __name__ == "__main__":
    unittest.main()
