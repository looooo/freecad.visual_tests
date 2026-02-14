"""
Self-tests for the visual test framework (no FreeCAD GUI).
Tests SSIM comparison logic from freecad.visual_tests.ssim.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from freecad.visual_tests.ssim import compare_images_ssim, ssim_value


def test_ssim_identical_arrays():
    """Identical arrays must yield SSIM = 1.0."""
    a = np.random.rand(50, 50).astype(np.float64)
    assert ssim_value(a, a) == pytest.approx(1.0, abs=1e-9)


def test_ssim_different_arrays():
    """Clearly different arrays must yield SSIM < 1.0."""
    ref = np.zeros((50, 50), dtype=np.float64)
    cand = np.ones((50, 50), dtype=np.float64)
    assert ssim_value(ref, cand) < 1.0


def test_ssim_similar_arrays_high_score():
    """Slightly noisy copy should still have high SSIM."""
    ref = np.random.rand(50, 50).astype(np.float64)
    noise = np.random.randn(50, 50).astype(np.float64) * 0.02
    cand = np.clip(ref + noise, 0.0, 1.0)
    assert ssim_value(ref, cand) >= 0.95


def test_ssim_via_image_files():
    """SSIM on two identical PNG files (framework code path, no FreeCAD)."""
    gray = (np.random.rand(40, 40) * 255).astype(np.uint8)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "img.png"
        Image.fromarray(gray, mode="L").save(path)
        result = compare_images_ssim(path, path, threshold=0.98)
        assert result.passed
        assert result.mean_diff == pytest.approx(0.0, abs=1e-6)


def test_feature_similarity_same_image():
    """Feature similarity of same image (or path) should be 1.0 (or very high)."""
    pytest.importorskip("cv2")
    from freecad.visual_tests.similarity import feature_similarity

    gray = (np.random.rand(120, 120) * 255).astype(np.uint8)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "img.png"
        Image.fromarray(gray, mode="L").save(path)
        sim = feature_similarity(path, path)
    assert sim >= 0.99


def test_feature_similarity_different_images():
    """Feature similarity of unrelated images should be low."""
    pytest.importorskip("cv2")
    from freecad.visual_tests.similarity import feature_similarity

    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "a.png"
        p2 = Path(tmp) / "b.png"
        Image.fromarray((np.random.rand(100, 100) * 255).astype(np.uint8), mode="L").save(p1)
        Image.fromarray((np.random.rand(100, 100) * 255).astype(np.uint8), mode="L").save(p2)
        sim = feature_similarity(p1, p2)
    assert sim < 0.5
