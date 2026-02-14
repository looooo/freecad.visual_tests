"""
Feature-based image similarity (ORB), robust to small perspective/scale changes.
Returns a value in [0, 1]; 1 = same content (e.g. slightly different viewpoint).
No FreeCAD dependency. Requires opencv (cv2).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


# Minimum inliers (after homography) to consider images related
_MIN_INLIERS = 10
# Inlier ratio (inliers / min(keypoints)) above which we cap at 1.0
# Same scene with slight perspective often gives 0.2–0.5
_INLIER_RATIO_FOR_ONE = 0.25


def feature_similarity(
    reference_path: Path | str,
    candidate_path: Path | str,
    max_size: int = 800,
) -> float:
    """
    Compare two images by ORB feature matching and geometric consistency.
    Robust to small perspective, scale, and rotation differences.
    Returns a value in [0, 1]: 1 = same content (e.g. slight perspective change).
    """
    import cv2  # type: ignore

    ref_path = Path(reference_path)
    cand_path = Path(candidate_path)
    ref = _load_grayscale(ref_path, max_size)
    cand = _load_grayscale(cand_path, max_size)
    if ref is None or cand is None:
        return 0.0

    orb = cv2.ORB_create(nfeatures=2000, edgeThreshold=31, patchSize=31)
    kp1, desc1 = orb.detectAndCompute(ref, None)
    kp2, desc2 = orb.detectAndCompute(cand, None)
    if desc1 is None or desc2 is None or len(kp1) < 4 or len(kp2) < 4:
        return 0.0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = matcher.knnMatch(desc1, desc2, k=2)
    good = []
    for m_n in matches:
        if len(m_n) != 2:
            continue
        m, n = m_n
        if m.distance < 0.75 * n.distance:
            good.append(m)
    if len(good) < 4:
        return 0.0

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if mask is None:
        return 0.0
    inlier_count = int(mask.sum())
    if inlier_count < _MIN_INLIERS:
        return 0.0

    n_min = min(len(kp1), len(kp2))
    inlier_ratio = inlier_count / max(1, n_min)
    # Scale so that inlier_ratio >= _INLIER_RATIO_FOR_ONE gives 1.0
    raw = inlier_ratio / _INLIER_RATIO_FOR_ONE
    return min(1.0, max(0.0, raw))


def _load_grayscale(path: Path, max_size: int):
    """Load image as 8-bit grayscale, optionally downscale for speed."""
    import cv2  # type: ignore

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img
