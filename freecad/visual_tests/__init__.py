"""
Visual regression tests for FreeCAD: capture views from .FCStd + metafile.yaml,
compare to references with SSIM, optional sketch/TechDraw handling.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

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


import numpy as np
from PIL import Image
import yaml

import FreeCAD  # type: ignore
import FreeCADGui  # type: ignore

from . import helper


# -----------------------------------------------------------------------------
# Environment snapshot helpers (for freecad_env.yaml)
# -----------------------------------------------------------------------------

def _try_config(*keys: str) -> Optional[str]:
    """First FreeCAD.ConfigGet(key) that returns a non-empty value."""
    for key in keys:
        try:
            v = FreeCAD.ConfigGet(key)
            if v:
                return v
        except Exception:
            pass
    return None


def _try_part_occ_version() -> Optional[str]:
    """Try to get OCCT version via Part module (e.g. OpenCASCADE get version string)."""
    try:
        import Part  # type: ignore
        if hasattr(Part, "getOCCVersion"):
            return Part.getOCCVersion()
        if hasattr(Part, "OCC_VERSION"):
            return str(Part.OCC_VERSION)
    except Exception:
        pass
    return None


def _try_pivy_version() -> Optional[str]:
    """Try to get Pivy (Python–Coin bindings) version."""
    try:
        import pivy  # type: ignore
        return getattr(pivy, "__version__", None)
    except Exception:
        pass
    return None


def _try_pivy_coin_version() -> Optional[str]:
    """Try to get Coin (Coin3D) version via Pivy – SoDB.getVersion()."""
    try:
        from pivy import coin  # type: ignore
        if hasattr(coin, "SoDB") and hasattr(coin.SoDB, "getVersion"):
            v = coin.SoDB.getVersion()
            if v is not None:
                return str(v).strip() or None
    except Exception:
        pass
    return None


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    passed: bool
    max_diff: float
    mean_diff: float
    diff_image_path: Optional[Path] = None

    def explain(self) -> str:
        return f"passed={self.passed}, max_diff={self.max_diff:.4f}, mean_diff={self.mean_diff:.4f}, diff_image={self.diff_image_path}"


@dataclass
class ViewConfig:
    id: str
    type: str
    camera: Dict[str, Any]
    display: Dict[str, Any]
    output_path: Path
    reference_path: Path
    diff_output_path: Path
    threshold: float  # minimum SSIM (0..1), e.g. 0.98
    sketch_edit: bool = False  # if True, enter sketch edit mode before capture and exit after
    sketch_name: Optional[str] = None  # name of sketch object; if None, use first Sketcher::SketchObject
    techdraw_page: Optional[str] = None  # TechDraw page name; None = first DrawPage


# -----------------------------------------------------------------------------
# Visual test session (FreeCAD GUI, documents, capture)
# -----------------------------------------------------------------------------

class VisualTestSession:
    """Manages a single FreeCAD GUI session for the test run."""

    def __init__(self) -> None:
        pass

    @classmethod
    def start(cls) -> "VisualTestSession":
        session = cls()

        # Ensure main window exists; in many environments this is a no-op
        try:  # pragma: no cover - depends on FreeCAD GUI
            FreeCADGui.showMainWindow()
        except Exception:
            # If the main window cannot be shown, we still return a session and
            # let individual operations raise more specific errors.
            pass

        # Disable FreeCAD's view animation features for deterministic screenshots.
        # This corresponds to unchecking "Enable animation" in the 3D View preferences.
        try:  # pragma: no cover - preference API
            view_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
            # Known keys used by FreeCAD for animated transitions:
            view_prefs.SetBool("UseAnimation", False)
            view_prefs.SetBool("EnableAnimation", False)
        except Exception:
            # Preference tuning is best-effort; do not hard-fail if something changes
            # in future FreeCAD versions.
            pass

        return session

    def shutdown(self) -> None:
        # Do not close FreeCAD automatically; often managed externally.
        pass

    def get_env_snapshot(self) -> Dict[str, Any]:
        """
        Return a dict with FreeCAD version and key dependency versions (OCCT, Python,
        Pivy, Coin) for reference/reproducibility alongside reference images.
        """
        fc_ver = list(FreeCAD.Version()) if hasattr(FreeCAD, "Version") else []
        freecad_version_str = ".".join(str(x) for x in fc_ver[:3]) if len(fc_ver) >= 3 else (fc_ver or None)
        out: Dict[str, Any] = {
            "freecad_version": freecad_version_str,
            "freecad_version_full": fc_ver,
            "python_version": sys.version.split()[0] if sys.version else None,
        }
        out["occt_version"] = _try_config("BuildVersionOCC", "OCC_VERSION", "BuildVersionOCCFull") or _try_part_occ_version()
        out["coin_version"] = _try_config("BuildVersionCoin", "BuildVersionCoin3D", "Coin3D_VERSION") or _try_pivy_coin_version()
        # Pivy (Python bindings for Coin)
        out["pivy_version"] = _try_pivy_version()
        return out

    # Document handling is intentionally very light for now.
    def open_document(self, path: str) -> Any:
        try:  # pragma: no cover - requires real FreeCAD
            return FreeCAD.openDocument(path)
        except Exception as exc:  # pragma: no cover - propagate for visibility
            raise RuntimeError(f"Failed to open FreeCAD document at '{path}'") from exc

    def close_document(self, doc: Any) -> None:
        if doc is None:
            return
        try:  # pragma: no cover - requires real FreeCAD
            FreeCAD.closeDocument(doc.Name)
        except Exception:
            # Best-effort close; do not fail the whole test on shutdown issues.
            pass

    def set_sketch_edit_mode(self, enter: bool, sketch_name: Optional[str] = None) -> None:
        """Enter or exit sketch edit mode. Delegates to helper."""
        helper.set_sketch_edit_mode(enter, sketch_name)

    def set_active_techdraw_page(self, page_name: Optional[str] = None) -> None:
        """Activate TechDraw page view. Delegates to helper."""
        helper.set_active_techdraw_page(page_name)

    def unset_techdraw_page(self) -> None:
        """Leave TechDraw page mode. Delegates to helper."""
        helper.unset_techdraw_page()

    def set_active_3d_view(self) -> None:
        """Activate the 3D view so that the next capture is the 3D scene (e.g. after a TechDraw view)."""
        try:
            FreeCADGui.activateView("Gui::View3DInventor", True)
        except Exception:
            pass

    def _get_3d_view(self) -> Any:
        """Return the 3D view of the active document (View3DInventor)."""
        try:
            gdoc = FreeCADGui.ActiveDocument
            if gdoc is None:
                return None
            views = list(gdoc.mdiViewsOfType("Gui::View3DInventor"))
            return views[0] if views else None
        except Exception:
            return None

    def execute_script(
        self, path: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Python script in the project folder. Context (e.g. session, base_dir)
        is passed in. Returns the script namespace so the caller can invoke optional
        hooks (e.g. teardown(session)) after views are captured.
        """
        namespace: Dict[str, Any] = {}
        if context:
            namespace.update(context)
        with open(path, "r", encoding="utf-8") as f:
            code = compile(f.read(), path, "exec")
        exec(code, namespace)
        return namespace

    def capture_view(self, view_config: ViewConfig, output_path: Path) -> None:
        """Capture the current FreeCAD view to output_path (PNG)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        width, height = view_config.display.get("size", [1600, 1200])

        try:  # pragma: no cover - requires real FreeCAD
            doc_gui = FreeCADGui.ActiveDocument
            if doc_gui is None:
                raise RuntimeError("No active FreeCAD GUI document for screenshot capture.")
            view = doc_gui.ActiveView
            try:
                if hasattr(view, "setAnimationEnabled"):
                    view.setAnimationEnabled(False)  # type: ignore[attr-defined]
            except Exception:
                pass

            # TechDraw: activate page, then capture (saveImage or MDI grab).
            if view_config.type == "techdraw" or view_config.techdraw_page is not None:
                helper.set_active_techdraw_page(view_config.techdraw_page)
                try:
                    helper.process_events_and_delay()
                    view = FreeCADGui.ActiveDocument.ActiveView
                    if view is not None and hasattr(view, "saveImage"):
                        view.saveImage(str(output_path), width, height, "Current")
                    else:
                        view = helper.get_techdraw_page_view()
                        if view is not None and hasattr(view, "saveImage"):
                            view.saveImage(str(output_path), width, height, "Current")
                        else:
                            helper.grab_mdi_active_subwindow(output_path, width, height)
                finally:
                    helper.unset_techdraw_page()
                return

            # 3D view: ensure View3DInventor is active, fit view, save.
            if view_config.type == "3d":
                self.set_active_3d_view()
                view = FreeCADGui.ActiveDocument.ActiveView
                if not hasattr(view, "saveImage"):
                    view = self._get_3d_view()
                if view is None or not hasattr(view, "saveImage"):
                    raise RuntimeError("No 3D view (Gui::View3DInventor) found for capture.")
                if hasattr(view, "viewAxonometric"):
                    view.viewAxonometric()
                if hasattr(view, "fitAll"):
                    view.fitAll()
                view.saveImage(str(output_path), width, height, "Current")
                return

            if hasattr(view, "saveImage"):
                view.saveImage(str(output_path), width, height, "Current")
            else:
                raise RuntimeError(
                    f"View for '{view_config.id}' has no saveImage (type={view_config.type})."
                )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to capture FreeCAD view for '{view_config.id}' "
                f"into '{output_path}'"
            ) from exc

    def compare_images_ssim(
        self, reference_path: Path, candidate_path: Path, threshold: float
    ) -> ComparisonResult:
        """Compare two images with SSIM (0..1, 1=identical). Pass if SSIM >= threshold. Numpy-only."""
        ref = Image.open(reference_path).convert("L")
        cand = Image.open(candidate_path).convert("L")

        if ref.size != cand.size:
            cand = cand.resize(ref.size)

        ref_arr = np.asarray(ref, dtype=np.float64) / 255.0
        cand_arr = np.asarray(cand, dtype=np.float64) / 255.0

        # Constants for stability (same scale as common SSIM for [0,1] data)
        c1 = 0.01 ** 2
        c2 = 0.03 ** 2

        mu_x = float(np.mean(ref_arr))
        mu_y = float(np.mean(cand_arr))
        var_x = float(np.var(ref_arr))
        var_y = float(np.var(cand_arr))
        cov_xy = float(np.mean(ref_arr * cand_arr) - mu_x * mu_y)

        ssim = (2 * mu_x * mu_y + c1) * (2 * cov_xy + c2)
        denom = (mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2)
        if denom > 0:
            ssim /= denom
        else:
            ssim = 0.0

        passed = ssim >= threshold
        diff_value = 1.0 - ssim
        diff_image_path: Optional[Path] = None
        if not passed:
            diff_arr = np.abs(ref_arr - cand_arr)
            diff_img = (np.clip(diff_arr, 0.0, 1.0) * 255.0).astype(np.uint8)
            diff_image = Image.fromarray(diff_img, mode="L")
            diff_image_path = candidate_path.parent / f"{candidate_path.stem}_ssim_diff.png"
            diff_image.save(diff_image_path)

        return ComparisonResult(
            passed=passed,
            max_diff=diff_value,
            mean_diff=diff_value,
            diff_image_path=diff_image_path,
        )


# -----------------------------------------------------------------------------
# Test case (metafile-driven views, run + compare)
# -----------------------------------------------------------------------------

class VisualTestCase:
    """One visual test: metafile.yaml + model, views, SSIM comparison."""

    def __init__(self, session: VisualTestSession, metafile_path: Union[str, Path]) -> None:
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
            display = view.get("display", {}) or {}
            output_cfg = view.get("output", {}) or {}

            filename = output_cfg.get("filename") or f"{vid}.png"
            threshold = float(output_cfg.get("threshold", threshold_default))
            sketch_edit = bool(view.get("sketch_edit", False))
            sketch_name = view.get("sketch_name")
            techdraw_page = view.get("techdraw_page")

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
                    sketch_edit=sketch_edit,
                    sketch_name=sketch_name,
                    techdraw_page=techdraw_page,
                )
            )
        return result

    def run_views_only(
        self,
        reference_mode: ReferenceMode = "compare",
        default_threshold: Optional[float] = None,
    ) -> None:
        """Capture each view, compare to reference with SSIM. reference_mode: compare | create_missing | update. Doc must be open."""
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
        import pytest  # local import to avoid hard runtime dependency in non-test code

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

            # Optional hook from project script (e.g. exit sketch edit mode)
            if script_namespace is not None:
                teardown = script_namespace.get("teardown")
                if callable(teardown):
                    teardown(self.session)
        finally:
            if doc is not None:
                self.session.close_document(doc)


def run_metafile_test(
    session: VisualTestSession,
    metafile_path: Union[str, Path],
    *,
    reference_mode: ReferenceMode = "compare",
    default_threshold: Optional[float] = None,
) -> None:
    """Open model from metafile, run views, compare with SSIM. metafile_path can be a directory (then metafile.yaml is used). Use from pytest with freecad_vis_session."""
    case = VisualTestCase(session, metafile_path)
    case.run(
        reference_mode=reference_mode,
        default_threshold=default_threshold,
    )

