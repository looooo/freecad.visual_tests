"""
Helpers for Sketcher (edit mode), TechDraw (page activation, capture), and 3D camera.
Uses FreeCAD/FreeCADGui; no dependency on VisualTestSession.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Dict, Optional

import FreeCAD  # type: ignore
import FreeCADGui  # type: ignore


# -----------------------------------------------------------------------------
# Sketcher
# -----------------------------------------------------------------------------

def set_sketch_edit_mode(enter: bool, sketch_name: Optional[str] = None) -> None:
    """Enter or exit sketch edit mode. If sketch_name is None, use first Sketcher::SketchObject."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return
    gui_doc = FreeCADGui.ActiveDocument
    if gui_doc is None:
        return
    if enter:
        obj = doc.getObject(sketch_name) if sketch_name else None
        if obj is None:
            for o in doc.Objects:
                if o.TypeId == "Sketcher::SketchObject":
                    obj = o
                    break
        if obj is None:
            raise RuntimeError("No Sketcher::SketchObject in document for sketch_edit view.")
        gui_doc.setEdit(obj, 0)
    else:
        gui_doc.resetEdit()


# -----------------------------------------------------------------------------
# 3D view background
# -----------------------------------------------------------------------------

def set_3d_view_background_white(view: Any) -> None:
    """Set the 3D viewer background to solid white (for reproducible screenshots)."""
    try:
        viewer = view.getViewer() if hasattr(view, "getViewer") else None
        if viewer is None:
            return
        # View3DInventorViewer: setBackgroundColorValue(r,g,b) or similar
        if hasattr(viewer, "setBackgroundColorValue"):
            viewer.setBackgroundColorValue(1.0, 1.0, 1.0)
        elif hasattr(viewer, "setBackgroundColor"):
            viewer.setBackgroundColor(1.0, 1.0, 1.0)
    except Exception:
        pass


def set_navi_cube_visible(view: Any, visible: bool) -> None:
    """Show or hide the 3D viewer navigation cube (so it does not appear in screenshots)."""
    try:
        viewer = view.getViewer() if hasattr(view, "getViewer") else None
        if viewer is not None and hasattr(viewer, "setEnabledNaviCube"):
            viewer.setEnabledNaviCube(visible)
    except Exception:
        pass


def set_3d_view_orientation(view: Any, orientation: str) -> None:
    """Set 3D view to a standard orientation (iso, front, top, bottom, left, right, rear)."""
    if not orientation:
        return
    o = orientation.lower().strip()
    try:
        if o in ("iso", "isometric") and hasattr(view, "viewIsometric"):
            view.viewIsometric()
        elif o in ("iso", "isometric") and hasattr(view, "viewAxonometric"):
            view.viewAxonometric()
        elif o == "front" and hasattr(view, "viewFront"):
            view.viewFront()
        elif o == "top" and hasattr(view, "viewTop"):
            view.viewTop()
        elif o == "bottom" and hasattr(view, "viewBottom"):
            view.viewBottom()
        elif o == "left" and hasattr(view, "viewLeft"):
            view.viewLeft()
        elif o == "right" and hasattr(view, "viewRight"):
            view.viewRight()
        elif o == "rear" and hasattr(view, "viewRear"):
            view.viewRear()
    except Exception:
        pass


def apply_3d_camera(view: Any, camera_config: Dict[str, Any]) -> None:
    """Apply camera settings (position, target, up, fov, projection) to the 3D view.
    Uses the view's camera node (Coin/pivy). If camera_config is empty or invalid, no-op.
    """
    if not camera_config:
        return
    try:
        cam = view.getCameraNode() if hasattr(view, "getCameraNode") else None
        if cam is None:
            return
        pos_list = camera_config.get("position")
        target_list = camera_config.get("target")
        up_list = camera_config.get("up", [0, 0, 1])
        fov_deg = camera_config.get("fov")
        projection = (camera_config.get("projection") or "perspective").lower()

        if pos_list and len(pos_list) >= 3:
            cam.position.setValue(
                float(pos_list[0]), float(pos_list[1]), float(pos_list[2])
            )
        if target_list and len(target_list) >= 3 and pos_list and len(pos_list) >= 3:
            # Orientation: camera looks along -Z in Coin; we want it to look at target.
            pos = FreeCAD.Vector(
                float(pos_list[0]), float(pos_list[1]), float(pos_list[2])
            )
            tgt = FreeCAD.Vector(
                float(target_list[0]), float(target_list[1]), float(target_list[2])
            )
            up = FreeCAD.Vector(
                float(up_list[0]), float(up_list[1]), float(up_list[2])
            )
            forward = tgt - pos
            if forward.Length > 1e-9:
                forward.normalize()
                right = forward.cross(up)
                if right.Length > 1e-9:
                    right.normalize()
                    cam_up = right.cross(forward)
                    if cam_up.Length > 1e-9:
                        cam_up.normalize()
                        # R columns = right, cam_up, -forward (camera axes in world)
                        r00, r01, r02 = right.x, cam_up.x, -forward.x
                        r10, r11, r12 = right.y, cam_up.y, -forward.y
                        r20, r21, r22 = right.z, cam_up.z, -forward.z
                        # Quaternion from rotation matrix (FreeCAD Q = (x,y,z,w))
                        trace = r00 + r11 + r22
                        if trace > 0:
                            s = 0.5 / math.sqrt(trace + 1.0)
                            qw = 0.25 / s
                            qx = (r21 - r12) * s
                            qy = (r02 - r20) * s
                            qz = (r10 - r01) * s
                        elif r00 > r11 and r00 > r22:
                            s = 2.0 * math.sqrt(1.0 + r00 - r11 - r22)
                            qw = (r21 - r12) / s
                            qx = 0.25 * s
                            qy = (r01 + r10) / s
                            qz = (r02 + r20) / s
                        elif r11 > r22:
                            s = 2.0 * math.sqrt(1.0 + r11 - r00 - r22)
                            qw = (r02 - r20) / s
                            qx = (r01 + r10) / s
                            qy = 0.25 * s
                            qz = (r12 + r21) / s
                        else:
                            s = 2.0 * math.sqrt(1.0 + r22 - r00 - r11)
                            qw = (r10 - r01) / s
                            qx = (r02 + r20) / s
                            qy = (r12 + r21) / s
                            qz = 0.25 * s
                        cam.orientation.setValue(qx, qy, qz, qw)

        if fov_deg is not None:
            fov_rad = math.radians(float(fov_deg))
            if hasattr(cam, "heightAngle"):
                cam.heightAngle.setValue(fov_rad)
            elif hasattr(cam, "height"):
                # Orthographic: height of view volume; approximate from fov and distance
                cam.height.setValue(2.0 * math.tan(fov_rad / 2.0) * 500.0)

        if projection == "orthographic" and hasattr(view, "getViewer"):
            viewer = view.getViewer()
            if viewer is not None and hasattr(viewer, "setCameraType"):
                viewer.setCameraType("Orthographic")
        elif projection == "perspective" and hasattr(view, "getViewer"):
            viewer = view.getViewer()
            if viewer is not None and hasattr(viewer, "setCameraType"):
                viewer.setCameraType("Perspective")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# TechDraw
# -----------------------------------------------------------------------------

def get_techdraw_drawpage(page_name: Optional[str] = None) -> Any:
    """Return the TechDraw DrawPage object. If page_name is None, return first TechDraw::DrawPage."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    page = doc.getObject(page_name) if page_name else None
    if page is None:
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawPage":
                page = o
                break
    return page


def set_active_techdraw_page(page_name: Optional[str] = None) -> None:
    """Activate the TechDraw page view (for GUI-based capture). If page_name is None, use first TechDraw::DrawPage."""
    page = get_techdraw_drawpage(page_name)
    if page is None:
        raise RuntimeError(f"No TechDraw::DrawPage found (page_name={page_name!r}).")
    gui_doc = FreeCADGui.ActiveDocument
    if gui_doc is None:
        raise RuntimeError("No active GUI document.")
    gui_doc.setEdit(page, 0)


def unset_techdraw_page() -> None:
    """Leave TechDraw page edit mode after capture."""
    gui_doc = FreeCADGui.ActiveDocument
    if gui_doc is not None:
        gui_doc.resetEdit()


def export_techdraw_page_to_png(
    page_name: Optional[str], output_path: Path, width: int, height: int
) -> None:
    """Export TechDraw page to PNG via TechDrawGui.exportPageAsSvg + Qt SVG→PNG. No GUI tab needed."""
    page = get_techdraw_drawpage(page_name)
    if page is None:
        raise RuntimeError(f"No TechDraw::DrawPage found (page_name={page_name!r}).")
    try:
        import TechDrawGui  # type: ignore
    except ImportError as e:
        raise RuntimeError("TechDrawGui module not available.") from e
    import tempfile
    with tempfile.TemporaryDirectory(prefix="freecad_techdraw_") as tmpdir:
        svg_path = Path(tmpdir) / "page.svg"
        TechDrawGui.exportPageAsSvg(page, str(svg_path))
        if not svg_path.exists():
            raise RuntimeError("TechDrawGui.exportPageAsSvg did not create file.")
        from PySide6 import QtGui, QtSvg
        renderer = QtSvg.QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            raise RuntimeError("SVG renderer invalid.")
        image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        image.fill(0xFFFFFFFF)
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        if not image.save(str(output_path), "PNG"):
            raise RuntimeError(f"Failed to save PNG to {output_path}")


def process_events_and_delay(delay_s: float = 0.4) -> None:
    """Let the GUI update (e.g. after TechDraw setEdit) before capturing."""
    try:
        from PySide6 import QtWidgets
        QtWidgets.QApplication.processEvents()
    except Exception:
        pass
    time.sleep(delay_s)
    try:
        from PySide6 import QtWidgets
        QtWidgets.QApplication.processEvents()
    except Exception:
        pass


def get_techdraw_page_view() -> Any:
    """Return the FreeCAD view that shows the TechDraw page (has saveImage, no viewAxonometric)."""
    try:
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return None
        for w in getattr(mw, "getWindows", lambda: [])():
            if hasattr(w, "saveImage") and not hasattr(w, "viewAxonometric"):
                return w
        return None
    except Exception:
        return None


def _activate_techdraw_mdi_subwindow() -> bool:
    """Activate the MDI subwindow that contains a QGraphicsView (TechDraw page). Returns True if found."""
    try:
        from PySide6 import QtWidgets
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return False
        mdi = mw.findChild(QtWidgets.QMdiArea)
        if mdi is None:
            return False
        for sub in mdi.subWindowList():
            w = sub.widget() if sub else None
            if w is None:
                continue
            if isinstance(w, QtWidgets.QGraphicsView):
                if sub is not None:
                    sub.raise_()
                    sub.activateWindow()
                return True
            if w.findChild(QtWidgets.QGraphicsView) is not None:
                if sub is not None:
                    sub.raise_()
                    sub.activateWindow()
                return True
        return False
    except Exception:
        return False


def grab_techdraw_page(output_path: Path, width: int, height: int) -> None:
    """Grab the TechDraw page as PNG. Activates TechDraw tab then grabs the MDI subwindow (not inner widget, to avoid deleted C++ object)."""
    try:
        from PySide6 import QtCore, QtWidgets
        for _ in range(2):
            try:
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass
            time.sleep(0.05)
        _activate_techdraw_mdi_subwindow()
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        time.sleep(0.05)
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            raise RuntimeError("No main window")
        mdi = mw.findChild(QtWidgets.QMdiArea)
        if mdi is None:
            raise RuntimeError("No MDI area")
        sub = mdi.activeSubWindow()
        if sub is None:
            raise RuntimeError("No active MDI subwindow (TechDraw tab may not be open)")
        # Grab the subwindow itself (QMdiSubWindow), not sub.widget(), to avoid "C++ object already deleted" when the inner QGraphicsView is recreated
        pixmap = sub.grab()
        if pixmap.isNull():
            raise RuntimeError("Subwindow grab returned null pixmap")
        if (pixmap.width(), pixmap.height()) != (width, height):
            pixmap = pixmap.scaled(
                width, height,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        if not pixmap.save(str(output_path), "PNG"):
            raise RuntimeError(f"Failed to save pixmap to {output_path}")
    except Exception as exc:
        raise RuntimeError(
            f"TechDraw grab failed: {exc}. "
            "Ensure the TechDraw page tab is visible after setEdit."
        ) from exc


def grab_mdi_active_subwindow(output_path: Path, width: int, height: int) -> None:
    """Grab the active MDI subwindow (e.g. TechDraw tab) as PNG. Fallback when saveImage is missing."""
    grab_techdraw_page(output_path, width, height)
