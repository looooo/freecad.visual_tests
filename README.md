# FreeCAD Visual Tests

Framework für visuelle Regressionstests mit FreeCAD: Modelle aus `.FCStd`-Dateien laden, definierte Ansichten rendern, mit Referenzbildern per **SSIM** vergleichen.

## Voraussetzungen

- **Linux** (getestet mit pixi/conda)
- [pixi](https://pixi.sh/) zum Verwalten der Umgebung
- FreeCAD wird über die pixi-Dependencies (conda-forge) bereitgestellt

## Schnellstart

```bash
# Umgebung einrichten (FreeCAD, pytest, Pillow, numpy, pyyaml)
pixi install

# Alle Tests ausführen (mit SSIM-Metriken in der Ausgabe)
pixi run test
```

Ohne sichtbaren Desktop (z. B. auf CI) Tests in virtueller Anzeige laufen lassen:

```bash
pixi run test-xvfb
```

## Projektstruktur

```
freecad.visual_tests/
├── freecad/visual_tests/
│   ├── __init__.py   # VisualTestSession, VisualTestCase, SSIM-Vergleich, run_metafile_test
│   └── helper.py     # Sketcher- und TechDraw-Logik (Edit-Modus, Seite aktivieren, MDI-Grab)
├── test/
│   ├── conftest.py   # Session-Fixture freecad_vis_session
│   └── data/
│       └── projekt_*/           # Ein Beispiel pro Projekt
│           ├── metafile.yaml   # Modell, Views, Schwellenwerte
│           ├── *.FCStd / *.fcstd
│           ├── test_projekt_*.py
│           ├── references/     # Referenzbilder + freecad_env.yaml
│           └── artifacts/      # Aktuelle Screenshots (gitignored)
├── pixi.toml
├── pyproject.toml
└── README.md
```

## Metafile (metafile.yaml)

Jeder Testordner enthält eine `metafile.yaml`, die Modell, Ansichten und Vergleichsparameter beschreibt.

### Top-Level

| Feld | Beschreibung |
|------|--------------|
| `version` | Konfigurationsversion (z. B. `1`) |
| `model` | Dateiname der FreeCAD-Datei (`.FCStd`/`.fcstd`) im gleichen Ordner |
| `description` | Kurzbeschreibung (optional) |

### default

| Feld | Bedeutung | Standard |
|------|------------|----------|
| `image_dir` | Ordner für Referenzbilder | `references` |
| `image_format` | Format (derzeit nur PNG genutzt) | `png` |
| `threshold` | Mindest-SSIM (0…1) pro View | `0.98` |

### views

Liste von Ansichten. Jede View hat:

| Feld | Pflicht | Beschreibung |
|------|--------|--------------|
| `id` | ja | Eindeutige ID (z. B. für Ausgabe und Fehlermeldungen) |
| `label` | nein | Lesbare Beschreibung |
| `type` | nein | `3d` (Standard) oder `techdraw` |
| `camera` | nein | Kamera-Parameter (position, target, up, fov, projection) – für 3D derzeit nur grob genutzt |
| `display` | nein | z. B. `size: [1600, 1200]` für Auflösung |
| `output` | nein | `filename`: Dateiname des Screenshots (Default: `{id}.png`) |
| `output.threshold` | nein | View-spezifischer SSIM-Schwellenwert (überschreibt default) |
| `sketch_edit` | nein | `true` = Sketch vor dem Screenshot in den Edit-Modus versetzen (wird vom Test gesteuert, siehe projekt_3) |
| `sketch_name` | nein | Name des Sketches; wenn leer, erster `Sketcher::SketchObject` |
| `techdraw_page` | nein | Name der TechDraw-Seite; `null` = erste `TechDraw::DrawPage` |

### Beispiel (3D-Views)

```yaml
version: 1
model: "MeinModell.FCStd"

default:
  image_dir: "references"
  threshold: 0.98

views:
  - id: "iso"
    type: "3d"
    display:
      size: [1600, 1200]
    output:
      filename: "iso.png"
  - id: "front"
    type: "3d"
    camera:
      position: [0, -500, 0]
      target: [0, 0, 0]
      up: [0, 0, 1]
    display:
      size: [1600, 1200]
    output:
      filename: "front.png"
```

### Beispiel (TechDraw)

```yaml
views:
  - id: "object_3d"
    type: "3d"
    output:
      filename: "object_3d.png"
  - id: "techdraw_page"
    type: "techdraw"
    techdraw_page: null   # erste DrawPage
    display:
      size: [1600, 1200]
    output:
      filename: "techdraw_page.png"
```

## Bildvergleich (SSIM)

- Es wird ausschließlich **SSIM** (Structural Similarity) verwendet (nur NumPy, keine weiteren Bild-Bibliotheken).
- Ein Wert von **1.0** = identisch; **0.98** = sehr ähnlich.
- `threshold` in der Metafile = **Mindest-SSIM**; der Test besteht, wenn `SSIM >= threshold`.
- Bei jedem Lauf werden pro View Zeilen ausgegeben, z. B.  
  `[projekt_1] engine_iso: SSIM=0.9990 (threshold=0.98) passed`

## Referenzen und Artefakte

- **references/**  
  Referenzbilder und `freecad_env.yaml`. Diese Dateien werden versioniert und definieren den „erwarteten“ Zustand.

- **artifacts/**  
  Bei jedem Testlauf erzeugte Screenshots und eine aktuelle `freecad_env.yaml`. Wird von `.gitignore` ausgeschlossen.

- **freecad_env.yaml**  
  Enthält u. a. `freecad_version`, `python_version`, `occt_version`, `coin_version`, `pivy_version` (für Reproduzierbarkeit). Wird bei jedem Lauf in `artifacts/` geschrieben und beim Erzeugen/Aktualisieren von Referenzen auch in `references/` geschrieben.

## Referenzen erzeugen oder aktualisieren

- Beim ersten Einrichten oder nach bewusster Änderung der erwarteten Ansicht:
  - Tests mit **create_missing_references=True** aufrufen (wie in den Beispiel-Tests).
  - Fehlende Referenzbilder werden aus den aktuellen Screenshots erzeugt; `freecad_env.yaml` in `references/` wird mitgeschrieben.
- Bestehende Referenzen überschreiben (z. B. nach FreeCAD-Update):
  - In `run_metafile_test(..., update_references=True)` setzen und Tests einmal laufen lassen.

## Beispiele (projekt_1–5)

| Projekt | Inhalt |
|---------|--------|
| **projekt_1** | Engine-Block, mehrere 3D-Ansichten (iso, front, top) |
| **projekt_2** | Part-Design-Tutorial, 3D-Ansichten |
| **projekt_3** | Sketcher: Dokument öffnen, Sketch in Edit-Modus, Screenshot, Edit beenden – eigener Testfluss |
| **projekt_4** | Assembly-Beispiel, 3D-Ansichten |
| **projekt_5** | TechDraw: 3D-Objekt + TechDraw-Seite als getrennte Bilder |

## Einen neuen Test schreiben

**Standardfall (Modell öffnen → alle Views aus metafile.yaml aufnehmen und vergleichen):**

```python
from pathlib import Path
from freecad.visual_tests import run_metafile_test

BASE_DIR = Path(__file__).resolve().parent

def test_mein_projekt(freecad_vis_session):
    run_metafile_test(
        freecad_vis_session,
        str(BASE_DIR / "metafile.yaml"),
        create_missing_references=True,  # Referenzen anlegen, wenn fehlend
    )
```

**Sonderfall (z. B. Sketcher-Edit vor dem Screenshot):**  
Dokument selbst öffnen, gewünschten Modus setzen (z. B. `setEdit(sketch)`), dann nur die View-Schleife ausführen:

```python
from freecad.visual_tests import VisualTestCase
import FreeCAD
import FreeCADGui

def test_sketcher(freecad_vis_session):
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
```

Die Fixture **freecad_vis_session** (in `test/conftest.py`) stellt eine gemeinsame FreeCAD-GUI-Session für alle Tests bereit.

## Pixi-Tasks

| Task | Beschreibung |
|------|--------------|
| `pixi run test` | Tests mit pytest ausführen; `-s` zeigt SSIM-Metriken |
| `pixi run test-xvfb` | Wie `test`, aber in virtueller Anzeige (xvfb) |
| `pixi run clean-artifacts` | Alle Dateien unter `test/**/artifacts/*` löschen |
| `pixi run clean-references` | Alle Dateien unter `test/**/references/*` löschen |
| `pixi run dev-install` | Paket im Entwicklungsmodus installieren (`pip install -e .`) |

## API (Kurzüberblick)

- **VisualTestSession**  
  `start()`, `open_document`, `close_document`, `set_sketch_edit_mode`, `set_active_techdraw_page`, `unset_techdraw_page`, `capture_view`, `compare_images_ssim`, `get_env_snapshot`, …

- **VisualTestCase**  
  Wird aus einer `metafile.yaml` aufgebaut.  
  `run(create_missing_references=..., update_references=..., default_threshold=...)`  
  `run_views_only(...)` – nur Views aufnehmen und vergleichen (Dokument muss bereits geöffnet sein).

- **run_metafile_test(session, metafile_path, create_missing_references=False, update_references=False, default_threshold=None)**  
  Bequem-Funktion: baut den VisualTestCase, öffnet das Modell, führt `run()` aus.

- **helper** (freecad.visual_tests.helper)  
  Sketcher: `set_sketch_edit_mode(enter, sketch_name=None)`.  
  TechDraw: `set_active_techdraw_page(page_name=None)`, `unset_techdraw_page()`, `process_events_and_delay()`, `get_techdraw_page_view()`, `grab_mdi_active_subwindow(output_path, width, height)`.

## Lizenz / Autor

Siehe `pyproject.toml` bzw. Projekt-Metadaten.
