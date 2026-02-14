"""
Visual regression tests for FreeCAD: capture views from .FCStd + metafile.yaml,
compare to references with SSIM, optional sketch/TechDraw handling.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

# "compare" = only compare, fail if reference missing
# "create_missing" = create if missing, compare if exists
# "update" = always write reference (create or overwrite), no comparison
ReferenceMode = Literal["compare", "create_missing", "update"]


def _resolve_metafile_path(path: Union[str, Path]) -> Path:
    """If path is a directory, return path / 'metafile.yaml'; otherwise return path as file."""
    p = Path(path).resolve()
    if p.is_dir():
        return p / "metafile.yaml"
    return p


import yaml

from .ssim import ComparisonResult

if TYPE_CHECKING:
    from .visual import VisualTestSession


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------


@dataclass
class ViewConfig:
    id: str
    type: str
    camera: Dict[str, Any]
    display: Dict[str, Any]
    output_path: Path
    reference_path: Path
    diff_output_path: Path
    threshold: float  # minimum similarity (0..1), e.g. 0.98 for SSIM
    fit_all: bool = True
    orientation: str = "iso"  # 3d with fit_all: iso, front, top, bottom, left, right, rear
    sketch_edit: bool = False
    sketch_name: Optional[str] = None
    techdraw_page: Optional[str] = None
    compare_method: str = "ssim"  # "ssim" (pixel) or "feature" (ORB, robust to perspective)


# -----------------------------------------------------------------------------
# Test case (metafile-driven views, run + compare)
# -----------------------------------------------------------------------------


class VisualTestCase:
    """One visual test: metafile.yaml + model, views, SSIM comparison."""

    def __init__(self, session: "VisualTestSession", metafile_path: Union[str, Path]) -> None:
        self.session = session
        self.metafile_path = _resolve_metafile_path(metafile_path)
        self.base_dir = self.metafile_path.parent
        self.config = self._load_yaml()
        self.views: List[ViewConfig] = self._build_views()

    def _load_yaml(self) -> Dict[str, Any]:
        with open(self.metafile_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _build_views(self) -> List[ViewConfig]:
        cfg = self.config
        defaults = cfg.get("default", {}) or {}
        image_dir = defaults.get("image_dir", "references")
        threshold_default = float(defaults.get("threshold", 0.98))

        refs_dir = self.base_dir / image_dir
        artifacts_dir = self.base_dir / "artifacts"
        refs_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        result: List[ViewConfig] = []
        for view in cfg.get("views", []):
            vid = view["id"]
            camera = view.get("camera", {}) or {}
            display = dict(view.get("display", {}) or {})
            display.setdefault("background", defaults.get("background", "white"))
            output_cfg = view.get("output", {}) or {}

            filename = output_cfg.get("filename") or f"{vid}.png"
            threshold = float(output_cfg.get("threshold", threshold_default))
            sketch_edit = bool(view.get("sketch_edit", False))
            sketch_name = view.get("sketch_name")
            techdraw_page = view.get("techdraw_page")
            fit_all = bool(view.get("fit_all", defaults.get("fit_all", True)))
            orientation = str(view.get("orientation", defaults.get("orientation", "iso"))).strip() or "iso"
            compare_method = str(view.get("compare_method", defaults.get("compare_method", "ssim"))).strip().lower()
            if compare_method not in ("ssim", "feature"):
                compare_method = "ssim"

            reference_path = refs_dir / filename
            output_path = artifacts_dir / filename
            diff_output_path = artifacts_dir / f"{Path(filename).stem}_diff.png"

            result.append(
                ViewConfig(
                    id=vid,
                    type=view.get("type", "3d"),
                    camera=camera,
                    display=display,
                    output_path=output_path,
                    reference_path=reference_path,
                    diff_output_path=diff_output_path,
                    threshold=threshold,
                    fit_all=fit_all,
                    orientation=orientation,
                    sketch_edit=sketch_edit,
                    sketch_name=sketch_name,
                    techdraw_page=techdraw_page,
                    compare_method=compare_method,
                )
            )
        return result

    def run_views_only(
        self,
        reference_mode: ReferenceMode = "compare",
        default_threshold: Optional[float] = None,
    ) -> None:
        """Capture each view, compare to reference with SSIM. Doc must be open."""
        import pytest

        write_refs = reference_mode in ("create_missing", "update")
        if self.views:
            env = {k: v for k, v in self.session.get_env_snapshot().items() if v is not None}
            artifacts_dir = self.views[0].output_path.parent
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            with open(artifacts_dir / "freecad_env.yaml", "w", encoding="utf-8") as f:
                yaml.dump(env, f, default_flow_style=False, allow_unicode=True)
            if write_refs:
                refs_dir = self.views[0].reference_path.parent
                refs_dir.mkdir(parents=True, exist_ok=True)
                with open(refs_dir / "freecad_env.yaml", "w", encoding="utf-8") as f:
                    yaml.dump(env, f, default_flow_style=False, allow_unicode=True)

        for view in self.views:
            if default_threshold is not None:
                view.threshold = default_threshold

            if view.sketch_edit:
                self.session.set_sketch_edit_mode(True, view.sketch_name)
                try:
                    self.session.capture_view(view, view.output_path)
                finally:
                    self.session.set_sketch_edit_mode(False)
            else:
                self.session.capture_view(view, view.output_path)

            if reference_mode == "update" or (reference_mode == "create_missing" and not view.reference_path.exists()):
                view.reference_path.parent.mkdir(parents=True, exist_ok=True)
                view.reference_path.write_bytes(view.output_path.read_bytes())
                action = "updated" if reference_mode == "update" else "created"
                print(f"  [{self.base_dir.name}] {view.id}: reference {action} (no comparison)", flush=True)
                continue

            if not view.reference_path.exists():
                pytest.fail(
                    f"Missing reference image for view '{view.id}': "
                    f"{view.reference_path}"
                )

            if view.compare_method == "feature":
                from .similarity import feature_similarity
                similarity, details = feature_similarity(
                    view.reference_path, view.output_path, return_details=True
                )
                passed = similarity >= view.threshold
                status = "passed" if passed else "FAILED"
                d = details
                print(
                    f"  [{self.base_dir.name}] {view.id}: feature={similarity:.4f} (threshold={view.threshold}) "
                    f"kp_ref={d['n_kp_ref']} kp_cand={d['n_kp_cand']} matches={d['n_matches']} inliers={d['n_inliers']} inlier_ratio={d['inlier_ratio']} {status}",
                    flush=True,
                )
                if not passed:
                    pytest.fail(
                        f"Visual regression detected for view '{view.id}'. "
                        f"feature_similarity={similarity:.4f} (threshold={view.threshold}) "
                        f"(reference={view.reference_path}, candidate={view.output_path})"
                    )
            else:
                result = self.session.compare_images_ssim(
                    view.reference_path,
                    view.output_path,
                    view.threshold,
                )
                ssim = 1.0 - result.mean_diff
                status = "passed" if result.passed else "FAILED"
                print(f"  [{self.base_dir.name}] {view.id}: SSIM={ssim:.4f} (threshold={view.threshold}) {status}", flush=True)
                if not result.passed:
                    msg = (
                        f"Visual regression detected for view '{view.id}'. "
                        f"{result.explain()} "
                        f"(reference={view.reference_path}, candidate={view.output_path})"
                    )
                    pytest.fail(msg)

    def run(
        self,
        reference_mode: ReferenceMode = "compare",
        default_threshold: Optional[float] = None,
    ) -> None:
        import pytest

        model = self.config.get("model")
        script = self.config.get("script")

        doc = None
        script_namespace: Optional[Dict[str, Any]] = None
        try:
            if model:
                doc_path = str((self.base_dir / model).resolve())
                doc = self.session.open_document(doc_path)

            if script:
                script_path = str((self.base_dir / script).resolve())
                script_namespace = self.session.execute_script(
                    script_path,
                    context={"session": self.session, "base_dir": self.base_dir},
                )

            self.run_views_only(
                reference_mode=reference_mode,
                default_threshold=default_threshold,
            )

            if script_namespace is not None:
                teardown = script_namespace.get("teardown")
                if callable(teardown):
                    teardown(self.session)
        finally:
            if doc is not None:
                self.session.close_document(doc)


def run_metafile_test(
    session: "VisualTestSession",
    metafile_path: Union[str, Path],
    *,
    reference_mode: ReferenceMode = "compare",
    default_threshold: Optional[float] = None,
) -> None:
    """Open model from metafile, run views, compare with SSIM. Use from pytest with freecad_vis_session."""
    case = VisualTestCase(session, metafile_path)
    case.run(
        reference_mode=reference_mode,
        default_threshold=default_threshold,
    )
