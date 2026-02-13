"""Sketcher test: open doc, enter sketch edit mode, capture view, exit edit, close."""
from pathlib import Path

import FreeCAD
import FreeCADGui

from freecad.visual_tests import VisualTestCase

BASE_DIR = Path(__file__).resolve().parent


def test_projekt_3_sketcher(freecad_vis_session):
    case = VisualTestCase(freecad_vis_session, str(BASE_DIR / "metafile.yaml"))
    doc = FreeCAD.openDocument(str(case.base_dir / case.config["model"]))
    try:
        sketch = next((o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"), None)
        if not sketch:
            raise RuntimeError("No Sketcher::SketchObject in document")
        FreeCADGui.ActiveDocument.setEdit(sketch, 0)
        try:
            case.run_views_only(create_missing_references=True)
        finally:
            FreeCADGui.ActiveDocument.resetEdit()
    finally:
        FreeCAD.closeDocument(doc.Name)
