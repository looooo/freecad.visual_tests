"""
Helpers for Sketcher (edit mode) and TechDraw (page activation, capture).
Uses FreeCAD/FreeCADGui; no dependency on VisualTestSession.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

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
# TechDraw
# -----------------------------------------------------------------------------

def set_active_techdraw_page(page_name: Optional[str] = None) -> None:
    """Activate the TechDraw page view. If page_name is None, use first TechDraw::DrawPage."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return
    gui_doc = FreeCADGui.ActiveDocument
    if gui_doc is None:
        return
    page = doc.getObject(page_name) if page_name else None
    if page is None:
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawPage":
                page = o
                break
    if page is None:
        raise RuntimeError(f"No TechDraw::DrawPage found (page_name={page_name!r}).")
    gui_doc.setEdit(page, 0)


def unset_techdraw_page() -> None:
    """Leave TechDraw page edit mode after capture."""
    gui_doc = FreeCADGui.ActiveDocument
    if gui_doc is not None:
        gui_doc.resetEdit()


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


def grab_mdi_active_subwindow(output_path: Path, width: int, height: int) -> None:
    """Grab the active MDI subwindow (e.g. TechDraw tab) as PNG. Fallback when saveImage is missing."""
    try:
        from PySide6 import QtCore, QtWidgets
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            raise RuntimeError("No main window")
        mdi = mw.findChild(QtWidgets.QMdiArea)
        if mdi is None:
            raise RuntimeError("No MDI area")
        sub = mdi.activeSubWindow()
        if sub is None:
            raise RuntimeError("No active MDI subwindow (TechDraw tab may not be open)")
        widget = sub.widget()
        if widget is None:
            raise RuntimeError("Active subwindow has no widget")
        pixmap = widget.grab()
        if pixmap.isNull():
            raise RuntimeError("Widget grab returned null pixmap")
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
            f"TechDraw MDI grab failed: {exc}. "
            "Ensure the TechDraw page tab is visible after setEdit."
        ) from exc
