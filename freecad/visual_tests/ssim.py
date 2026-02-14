"""
SSIM image comparison (no FreeCAD dependency).
Used by the visual test framework and by selftests.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


@dataclass
class ComparisonResult:
    passed: bool
    max_diff: float
    mean_diff: float
    diff_image_path: Optional[Path] = None

    def explain(self) -> str:
        return f"passed={self.passed}, max_diff={self.max_diff:.4f}, mean_diff={self.mean_diff:.4f}, diff_image={self.diff_image_path}"


def ssim_value(ref_arr: np.ndarray, cand_arr: np.ndarray) -> float:
    """Compute SSIM for two arrays (0..1, 1=identical). Same formula as compare_images_ssim. Expects same shape (caller resizes if needed)."""
    ref_arr = np.asarray(ref_arr, dtype=np.float64)
    cand_arr = np.asarray(cand_arr, dtype=np.float64)
    if ref_arr.shape != cand_arr.shape:
        cand_arr = np.asarray(Image.fromarray((np.clip(cand_arr, 0, 1) * 255).astype(np.uint8)).resize((ref_arr.shape[1], ref_arr.shape[0])), dtype=np.float64) / 255.0
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    mu_x = float(np.mean(ref_arr))
    mu_y = float(np.mean(cand_arr))
    var_x = float(np.var(ref_arr))
    var_y = float(np.var(cand_arr))
    cov_xy = float(np.mean(ref_arr * cand_arr) - mu_x * mu_y)
    ssim = (2 * mu_x * mu_y + c1) * (2 * cov_xy + c2)
    denom = (mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2)
    return (ssim / denom) if denom > 0 else 0.0


def compare_images_ssim(
    reference_path: Path,
    candidate_path: Path,
    threshold: float,
    diff_output_path: Optional[Path] = None,
) -> ComparisonResult:
    """Compare two images with SSIM (0..1, 1=identical). Pass if SSIM >= threshold."""
    ref = Image.open(reference_path).convert("L")
    cand = Image.open(candidate_path).convert("L")
    if ref.size != cand.size:
        cand = cand.resize(ref.size)
    ref_arr = np.asarray(ref, dtype=np.float64) / 255.0
    cand_arr = np.asarray(cand, dtype=np.float64) / 255.0
    ssim = ssim_value(ref_arr, cand_arr)
    passed = ssim >= threshold
    diff_value = 1.0 - ssim
    out_path: Optional[Path] = None
    if not passed and diff_output_path is not None:
        diff_arr = np.abs(ref_arr - cand_arr)
        diff_img = (np.clip(diff_arr, 0.0, 1.0) * 255.0).astype(np.uint8)
        Image.fromarray(diff_img, mode="L").save(diff_output_path)
        out_path = diff_output_path
    return ComparisonResult(
        passed=passed,
        max_diff=diff_value,
        mean_diff=diff_value,
        diff_image_path=out_path,
    )
