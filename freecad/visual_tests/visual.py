"""
FreeCAD-dependent visual test session: GUI, documents, capture.
Import this module only when FreeCAD is available (e.g. in tests under xvfb).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import FreeCAD  # type: ignore
import FreeCADGui  # type: ignore

from . import helper
from .ssim import ComparisonResult, compare_images_ssim as _compare_images_ssim


def _try_config(*keys: str) -> Optional[str]:
    """First FreeCAD.ConfigGet(key) that returns a non-empty value."""
    for key in keys:
        v = FreeCAD.ConfigGet(key)
        if v:
            return v
    return None


def _try_part_occ_version() -> Optional[str]:
    """Get OCCT version via Part module (e.g. OpenCASCADE get version string)."""
    import Part  # type: ignore
    if hasattr(Part, "getOCCVersion"):
        return Part.getOCCVersion()
    if hasattr(Part, "OCC_VERSION"):
        return str(Part.OCC_VERSION)
    return None


def _try_pivy_version() -> Optional[str]:
    """Get Pivy (Python–Coin bindings) version."""
    import pivy  # type: ignore
    return getattr(pivy, "__version__", None)


def _try_pivy_coin_version() -> Optional[str]:
    """Get Coin (Coin3D) version via Pivy – SoDB.getVersion()."""
    from pivy import coin  # type: ignore
    if hasattr(coin, "SoDB") and hasattr(coin.SoDB, "getVersion"):
        v = coin.SoDB.getVersion()
        if v is not None:
            return str(v).strip() or None
    return None


class VisualTestSession:
    """Manages a single FreeCAD GUI session for the test run."""

    def __init__(self) -> None:
        pass

    @classmethod
    def start(cls) -> "VisualTestSession":
        session = cls()

        # Ensure main window exists; in many environments this is a no-op
        FreeCADGui.showMainWindow()

        # Disable FreeCAD's view animation features for deterministic screenshots.
        view_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        view_prefs.SetBool("UseAnimation", False)
        view_prefs.SetBool("EnableAnimation", False)

        # Use Ubuntu 22.04 default Qt font everywhere for consistent text rendering.
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont("Ubuntu", 11))

        return session

    def shutdown(self) -> None:
        """Close all documents and process events so views are destroyed before process exit."""
        doc_names = list(FreeCAD.listDocuments().keys())
        for name in doc_names:
            FreeCAD.closeDocument(name)
        from PySide6 import QtWidgets
        for _ in range(5):
            QtWidgets.QApplication.processEvents()
            time.sleep(0.05)

    def get_env_snapshot(self) -> Dict[str, Any]:
        """Return a dict with FreeCAD version and key dependency versions for reference images."""
        fc_ver = list(FreeCAD.Version()) if hasattr(FreeCAD, "Version") else []
        freecad_version_str = ".".join(str(x) for x in fc_ver[:3]) if len(fc_ver) >= 3 else (fc_ver or None)
        out: Dict[str, Any] = {
            "freecad_version": freecad_version_str,
            "freecad_version_full": fc_ver,
            "python_version": sys.version.split()[0] if sys.version else None,
        }
        out["occt_version"] = _try_config("BuildVersionOCC", "OCC_VERSION", "BuildVersionOCCFull") or _try_part_occ_version()
        out["coin_version"] = _try_config("BuildVersionCoin", "BuildVersionCoin3D", "Coin3D_VERSION") or _try_pivy_coin_version()
        out["pivy_version"] = _try_pivy_version()
        return out

    def open_document(self, path: str) -> Any:
        try:  # pragma: no cover - requires real FreeCAD
            return FreeCAD.openDocument(path)
        except Exception as exc:
            raise RuntimeError(f"Failed to open FreeCAD document at '{path}'") from exc

    def close_document(self, doc: Any) -> None:
        if doc is None:
            return
        FreeCAD.closeDocument(doc.Name)

    def set_sketch_edit_mode(self, enter: bool, sketch_name: Optional[str] = None) -> None:
        helper.set_sketch_edit_mode(enter, sketch_name)

    def set_active_techdraw_page(self, page_name: Optional[str] = None) -> None:
        helper.set_active_techdraw_page(page_name)

    def unset_techdraw_page(self) -> None:
        helper.unset_techdraw_page()

    def set_active_3d_view(self) -> None:
        FreeCADGui.activateView("Gui::View3DInventor", True)

    def _get_3d_view(self) -> Any:
        gdoc = FreeCADGui.ActiveDocument
        if gdoc is None:
            return None
        views = list(gdoc.mdiViewsOfType("Gui::View3DInventor"))
        return views[0] if views else None

    def execute_script(
        self, path: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        namespace: Dict[str, Any] = {}
        if context:
            namespace.update(context)
        with open(path, "r", encoding="utf-8") as f:
            code = compile(f.read(), path, "exec")
        exec(code, namespace)
        return namespace

    def capture_view(self, view_config: "ViewConfig", output_path: Path) -> None:
        """Capture the current FreeCAD view to output_path (PNG)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        width, height = view_config.display.get("size", [1600, 1200])

        try:  # pragma: no cover - requires real FreeCAD
            doc_gui = FreeCADGui.ActiveDocument
            if doc_gui is None:
                raise RuntimeError("No active FreeCAD GUI document for screenshot capture.")
            view = doc_gui.ActiveView
            if hasattr(view, "setAnimationEnabled"):
                view.setAnimationEnabled(False)  # type: ignore[attr-defined]

            if view_config.type == "techdraw" or view_config.techdraw_page is not None:
                helper.process_events_and_delay(0.3)
                helper.export_techdraw_page_to_png(
                    view_config.techdraw_page, output_path, width, height
                )
                return

            if view_config.type == "3d":
                self.set_active_3d_view()
                view = FreeCADGui.ActiveDocument.ActiveView
                if not hasattr(view, "saveImage"):
                    view = self._get_3d_view()
                if view is None or not hasattr(view, "saveImage"):
                    raise RuntimeError("No 3D view (Gui::View3DInventor) found for capture.")
                helper.set_navi_cube_visible(view, False)
                helper.process_events_and_delay(0.1)
                if view_config.display.get("background") == "white":
                    helper.set_3d_view_background_white(view)
                if view_config.fit_all:
                    helper.set_3d_view_orientation(view, view_config.orientation)
                    if hasattr(view, "fitAll"):
                        view.fitAll()
                else:
                    cam = view_config.camera or {}
                    if cam.get("position") and cam.get("target"):
                        helper.apply_3d_camera(view, cam)
                        helper.process_events_and_delay(0.2)
                    else:
                        if hasattr(view, "viewAxonometric"):
                            view.viewAxonometric()
                        if hasattr(view, "fitAll"):
                            view.fitAll()
                helper.process_events_and_delay(0.3)
                view.saveImage(str(output_path), width, height, "Current")
                return

            if hasattr(view, "saveImage"):
                helper.process_events_and_delay(0.3)
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
        """Compare two images with SSIM. Delegates to ssim module."""
        diff_path = candidate_path.parent / f"{candidate_path.stem}_ssim_diff.png"
        return _compare_images_ssim(
            reference_path, candidate_path, threshold, diff_output_path=diff_path
        )
