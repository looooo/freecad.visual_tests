# FreeCAD Visual Tests

Framework for visual regression testing with FreeCAD: load models from `.FCStd` files, render defined views, and compare against reference images using **SSIM**.

## Requirements

- **Linux** (tested with pixi/conda)
- [pixi](https://pixi.sh/) for environment management
- FreeCAD is provided via pixi dependencies (conda-forge)

## Quick start

```bash
# Set up environment (FreeCAD, pytest, Pillow, numpy, pyyaml)
pixi install

# Run all tests (SSIM metrics printed to stdout)
pixi run test
```

Run tests in a virtual display when no desktop is available (e.g. on CI):

```bash
pixi run test-xvfb
```

### Docker (reproducible environment)

You can run the tests in a Docker container with a fixed environment (Debian Bookworm, pixi, FreeCAD from conda-forge) for long-term reproducibility.

```bash
# Build image (uses pixi.lock if present)
docker build -t freecad-visual-tests .

# Run tests (default entrypoint = test-xvfb)
docker run --rm freecad-visual-tests

# Generate reference images (update mode)
docker run --rm freecad-visual-tests run create-references
```

**Long-term reproducibility (e.g. 10 years):**

- **Keep `pixi.lock` in the repo:** `pixi install --locked` in the Dockerfile uses the exact package versions from the lock file.
- **Pin the base image:** For strict reproducibility, pin the Debian image by digest (see comment in the Dockerfile): run `docker pull debian:bookworm-slim`, then use the digest from `docker image inspect` as `FROM debian@sha256:...` in the Dockerfile.
- **Archive the built image:** Build the image once and save it to a registry or as a tar file (`docker save`) so you can re-run without rebuilding.

## Project structure

```
freecad.visual_tests/
├── freecad/visual_tests/
│   ├── __init__.py   # ViewConfig, VisualTestCase, run_metafile_test (no FreeCAD import)
│   ├── visual.py     # VisualTestSession, FreeCAD-dependent capture/session
│   └── helper.py     # Sketcher and TechDraw logic (edit mode, page activation, export)
├── test/
│   ├── conftest.py   # Session fixture freecad_vis_session
│   └── data/
│       └── projekt_*/           # One example per project
│           ├── metafile.yaml   # Model, views, thresholds
│           ├── *.FCStd / *.fcstd
│           ├── test_projekt_*.py
│           ├── references/     # Reference images + freecad_env.yaml
│           └── artifacts/     # Current screenshots (gitignored)
├── pixi.toml
├── pyproject.toml
└── README.md
```

## Metafile (metafile.yaml)

Each test folder contains a `metafile.yaml` that describes the model, views, and comparison parameters.

### Top-level

| Field | Description |
|-------|-------------|
| `version` | Config version (e.g. `1`); for future compatibility – version is bumped when the metafile format changes. |
| `model` | FreeCAD file name (`.FCStd`/`.fcstd`) in the same folder |
| `description` | Short description (optional) |

### default

All fields are optional; sensible defaults allow a minimal metafile.

| Field | Meaning | Default |
|-------|---------|---------|
| `image_dir` | Folder for reference images | `references` |
| `image_format` | Image format (only PNG supported so far) | `png` |
| `threshold` | Minimum SSIM (0…1) per view | `0.98` |
| `fit_all` | 3D: when `true` use orientation + fitAll; when `false` use camera from view | `true` |
| `orientation` | 3D with fit_all: default orientation (`iso`, `front`, `top`, …) | `iso` |

### views

List of views. Each view has:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique ID (e.g. for output and error messages) |
| `label` | no | Human-readable description |
| `type` | no | `3d` (default) or `techdraw` |
| `camera` | no | Camera (position, target, up, fov, projection); only used when `fit_all: false` |
| `fit_all` | no | 3D: `true` = orientation + fitAll (default), `false` = apply camera from view/`camera` |
| `orientation` | no | 3D with fit_all: `iso`, `front`, `top`, `bottom`, `left`, `right`, `rear` (default: `iso`) |
| `display` | no | e.g. `size: [1600, 1200]` for resolution (3D background is always white) |
| `output` | no | `filename`: screenshot file name (default: `{id}.png`) |
| `output.threshold` | no | View-specific SSIM threshold (overrides default) |
| `sketch_edit` | no | `true` = put sketch in edit mode before screenshot (see projekt_3) |
| `sketch_name` | no | Sketch object name; if empty, first `Sketcher::SketchObject` |
| `techdraw_page` | no | TechDraw page name; `null` = first `TechDraw::DrawPage` |

### Example (3D views)

```yaml
version: 1
model: "MyModel.FCStd"

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

### Example (TechDraw)

```yaml
views:
  - id: "object_3d"
    type: "3d"
    output:
      filename: "object_3d.png"
  - id: "techdraw_page"
    type: "techdraw"
    techdraw_page: null   # first DrawPage
    display:
      size: [1600, 1200]
    output:
      filename: "techdraw_page.png"
```

## Image comparison (SSIM)

- Only **SSIM** (Structural Similarity) is used (NumPy only, no other image libraries).
- A value of **1.0** = identical; **0.98** = very similar.
- `threshold` in the metafile = **minimum SSIM**; the test passes when `SSIM >= threshold`.
- Each run prints one line per view, e.g.  
  `[projekt_1] engine_iso: SSIM=0.9990 (threshold=0.98) passed`

## References and artifacts

- **references/**  
  Reference images and `freecad_env.yaml`. These files are versioned and define the “expected” state.

- **artifacts/**  
  Screenshots and a current `freecad_env.yaml` produced on each test run. Excluded by `.gitignore`.

- **freecad_env.yaml**  
  Contains e.g. `freecad_version`, `python_version`, `occt_version`, `coin_version`, `pivy_version` (for reproducibility). Written to `artifacts/` on every run and also to `references/` when creating or updating references.

## Creating or updating references

**References via GitHub Action (CI):** Run the **Update reference images** workflow manually under Actions (`workflow_dispatch`). It renders all views in the CI environment, commits the new reference images and `freecad_env.yaml`, and pushes to the current branch so references match the test environment on GitHub.

**Locally**, a single parameter **reference_mode** controls behaviour:

| reference_mode   | Meaning |
|-----------------|---------|
| `"compare"`     | Compare only; fail if a reference is missing (default). |
| `"create_missing"` | Create missing references from the current run, compare existing ones. |
| `"update"`      | Write all references (create or overwrite), no comparison (e.g. after FreeCAD update). |

Example: `run_metafile_test(session, BASE_DIR, reference_mode="create_missing")`.

## When to use what

| Goal | Approach |
|------|----------|
| Normal tests (one model, 3D/TechDraw/Sketcher via metafile) | `run_metafile_test(session, BASE_DIR, reference_mode="compare")` (or `"create_missing"` when creating references for the first time). |
| Create references once | `reference_mode="create_missing"`. |
| Regenerate references after FreeCAD/environment change | `reference_mode="update"`. |
| Custom document or mode handling (rare) | Build `VisualTestCase(session, BASE_DIR)`, open/close document yourself, call `case.run_views_only(reference_mode=...)`. Close document afterwards. |

## Examples (projekt_1–5)

| Project | Content |
|---------|---------|
| **projekt_1** | Engine block, multiple 3D views (iso, front, top) |
| **projekt_2** | Part Design tutorial, 3D views |
| **projekt_3** | Sketcher: `sketch_edit: true` in metafile, standard `run_metafile_test` |
| **projekt_4** | Assembly example, 3D views |
| **projekt_5** | TechDraw: 3D object + TechDraw page as separate images |

## Writing a new test

**Standard case:** Pass a folder with `metafile.yaml` (path can be directory or file; if directory, `metafile.yaml` is used automatically):

```python
from pathlib import Path
from freecad.visual_tests import run_metafile_test

BASE_DIR = Path(__file__).resolve().parent

def test_my_project(freecad_vis_session):
    run_metafile_test(
        freecad_vis_session,
        BASE_DIR,
        reference_mode="create_missing",  # create references when missing
    )
```

**Sketcher (edit mode):** Set `sketch_edit: true` (and optionally `sketch_name`) on the view in the metafile – the framework opens the document, puts the sketch in edit mode, takes the screenshot, and leaves edit mode. No extra test code needed (see projekt_3).

**Use a looser threshold (e.g. locally):** `run_metafile_test(session, BASE_DIR, default_threshold=0.95)` – overrides the metafile default for that run.

**Custom flow (rare):** If you control document or mode yourself: build `VisualTestCase(session, BASE_DIR)`, open the document, then call `case.run_views_only(reference_mode=...)`. Close the document yourself afterwards.

**Session:** The **freecad_vis_session** fixture (in `test/conftest.py`) provides a shared FreeCAD GUI session for all tests. For scripts outside pytest: `from freecad.visual_tests.visual import VisualTestSession`; call `session = VisualTestSession.start()`, then e.g. `run_metafile_test(session, path)`; call `session.shutdown()` at the end.

## Known limitations

- **Platform:** Tested on Linux (pixi/conda). Without a visible desktop (e.g. CI), a virtual display is required (`pixi run test-xvfb`).
- **One GUI session per run:** All tests share one FreeCAD GUI session (fixture); documents are opened and closed in sequence.
- **Order:** Test order can matter with shared documents or global FreeCAD settings.
- **One model per metafile:** Each `metafile.yaml` references exactly one `.FCStd` file; multiple models per metafile are not supported.
- **Shutdown:** On exit, `session.shutdown()` closes all open documents and processes Qt events to avoid crashes at process end (e.g. in `View3DInventor` destructor). If a segfault still occurs afterwards, the test result is already fixed.

## Pixi tasks

| Task | Description |
|------|-------------|
| `pixi run test` | Run tests with pytest; `-s` shows SSIM metrics |
| `pixi run test-xvfb` | Same as `test` but in xvfb; exit code 0/1 reflects test result even if FreeCAD crashes on shutdown |
| `pixi run create-references` | Create or update reference images (runs tests in xvfb with `VISUAL_TEST_REFERENCE_MODE=update`) |
| `pixi run clean-artifacts` | Remove all files under `test/**/artifacts/*` |
| `pixi run clean-references` | Remove all files under `test/**/references/*` |
| `pixi run dev-install` | Install package in development mode (`pip install -e .`) |

## API (overview)

### Public API (for normal tests)

- **run_metafile_test(session, metafile_path, reference_mode="compare", default_threshold=None)**  
  Convenience function for most cases. **metafile_path** can be a folder (then `metafile.yaml`) or a file path. Opens the model, runs all views, compares with references.

- **VisualTestCase(session, metafile_path)**  
  Built from a `metafile.yaml`.  
  `run(reference_mode=..., default_threshold=...)` – open model, run views, close model.  
  `run_views_only(reference_mode=..., default_threshold=...)` – views only (document must already be open; for custom flow).

- **VisualTestSession** (from `freecad.visual_tests.visual`)  
  `start()`, `shutdown()`, `open_document`, `close_document`, `get_env_snapshot`. Provided in pytest via the **freecad_vis_session** fixture.

### Advanced use / helpers

- **helper** (freecad.visual_tests.helper) – Sketcher and TechDraw control if you implement the flow yourself:  
  `set_sketch_edit_mode(enter, sketch_name=None)`, `set_active_techdraw_page(page_name=None)`, `unset_techdraw_page()`, `process_events_and_delay()`, `get_techdraw_page_view()`, `grab_mdi_active_subwindow(output_path, width, height)`.  
  Via the session: `session.set_sketch_edit_mode`, `session.set_active_techdraw_page`, `session.unset_techdraw_page`.

## License / author

See `pyproject.toml` or project metadata.
