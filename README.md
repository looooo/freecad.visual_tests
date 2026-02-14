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

This uses `scripts/run_visual_tests_xvfb.py` (wraps pytest with `xvfb-run`). The script requires **xvfb** and **xauth** to be installed (e.g. `apt-get install xvfb xauth`).

**Optional: Docker for reproducibility**

For a fixed environment (e.g. same OS, pixi, FreeCAD from conda-forge), use a Docker image that installs pixi, xvfb, xauth, runs `pixi install --locked`, and uses `pixi run test-xvfb` as the default command. Keep `pixi.lock` in the repo so `pixi install --locked` reproduces exact versions. Pin the base image by digest for long-term reproducibility.

## Project structure

```
freecad.visual_tests/
├── freecad/visual_tests/
│   ├── __init__.py   # discover_projects, run_metafile_test, VisualTestCase, __version__
│   ├── ssim.py       # SSIM comparison (ComparisonResult, compare_images_ssim); no FreeCAD
│   ├── similarity.py # Feature-based similarity (ORB); no FreeCAD; requires opencv
│   ├── visual.py     # VisualTestSession, FreeCAD-dependent capture/session
│   └── helper.py     # Sketcher and TechDraw (edit mode, page activation, export)
├── scripts/
│   └── run_visual_tests_xvfb.py   # Runs pytest under xvfb; used by test-xvfb / create-references-xvfb
├── test/
│   ├── conftest.py   # Session fixture freecad_vis_session
│   ├── test_visual_projects.py   # Parametrised test over all projects (no per-project Python)
│   ├── test_framework_selftest.py # SSIM unit tests, no FreeCAD (pixi run selftest)
│   └── data/
│       └── projekt_*/           # One folder per project (discovered by metafile.yaml)
│           ├── metafile.yaml    # Model, views, thresholds
│           ├── *.FCStd / *.fcstd
│           ├── references/     # Reference images + freecad_env.yaml
│           └── artifacts/      # Current screenshots (gitignored)
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
| `sketch_edit` | no | `true` = put sketch in edit mode before screenshot (e.g. projekt_3) |
| `sketch_name` | no | Sketch object name; if empty, first `Sketcher::SketchObject` |
| `techdraw_page` | no | TechDraw page name; `null` = first `TechDraw::DrawPage` |
| `compare_method` | no | `ssim` (default, pixel-based) or `feature` (ORB, robust to small perspective/scale changes) |

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

## Image comparison

### SSIM (default)

- **SSIM** (Structural Similarity) is implemented in `freecad.visual_tests.ssim` (NumPy + PIL only; no FreeCAD). This allows running SSIM-related tests without a GUI (e.g. `pixi run selftest`).
- A value of **1.0** = identical; **0.98** = very similar.
- `threshold` in the metafile = **minimum SSIM**; the test passes when `SSIM >= threshold`.
- Each run prints one line per view, e.g.  
  `[projekt_1] engine_iso: SSIM=0.9990 (threshold=0.98) passed`  
  (Project name = folder name under `test/data/`.)

### Feature-based (ORB)

- For views where the camera or perspective may vary slightly (e.g. different systems), set **`compare_method: "feature"`** in the view (or in `default`). This uses ORB keypoints + homography inliers and returns a similarity in **[0, 1]**.
- **1.0** = same content (e.g. same scene with a slight perspective or scale difference). Implemented in `freecad.visual_tests.similarity.feature_similarity` (requires **opencv**). Lightweight (no deep learning); robust to small rotation, scale, and perspective changes.
- Same `threshold` semantics: test passes when `similarity >= threshold` (e.g. `0.85`–`0.95` for feature).

## References and artifacts

- **references/**  
  Reference images and `freecad_env.yaml`. These files are versioned and define the “expected” state.

- **artifacts/**  
  Screenshots and a current `freecad_env.yaml` produced on each test run. Excluded by `.gitignore`.

- **freecad_env.yaml**  
  Contains e.g. `freecad_version`, `python_version`, `occt_version`, `coin_version`, `pivy_version` (for reproducibility). Written to `artifacts/` on every run and also to `references/` when creating or updating references.

## Creating or updating references

**References via GitHub Action (CI):** Run the **Update reference images** workflow manually under Actions (`workflow_dispatch`). It renders all views in the CI environment, commits the new reference images and `freecad_env.yaml`, and pushes to the current branch.

**Locally**, either run `pixi run create-references-xvfb` (writes all references), or set env **VISUAL_TEST_REFERENCE_MODE** (see below). If you call the API directly, pass **reference_mode**; if `None`, the env var is used (default: `create_missing`).

| reference_mode   | Meaning |
|-----------------|---------|
| `"compare"`     | Compare only; fail if a reference is missing (default when env not set). |
| `"create_missing"` | Create missing references from the current run, compare existing ones. (Default when env is unset.) |
| `"update"`      | Write all references (create or overwrite), no comparison (e.g. after FreeCAD update). |

Example: `run_metafile_test(session, project_dir)` (uses env); or `run_metafile_test(session, project_dir, reference_mode="create_missing")`.

## When to use what

| Goal | Approach |
|------|----------|
| Normal tests (one model, 3D/TechDraw/Sketcher via metafile) | `run_metafile_test(session, project_dir)` (uses env) or pass `reference_mode="compare"` / `"create_missing"`. |
| Create references once | `reference_mode="create_missing"` or env `VISUAL_TEST_REFERENCE_MODE=create_missing`. |
| Regenerate references after FreeCAD/environment change | `reference_mode="update"` or `pixi run create-references-xvfb`. |
| Custom document or mode handling (rare) | Build `VisualTestCase(session, metafile_path)`, open/close document yourself, call `case.run_views_only(reference_mode=...)`. Close document afterwards. |

## Examples (projekt_1–5)

| Project | Content |
|---------|---------|
| **projekt_1** | Engine block, multiple 3D views (iso, front, top) |
| **projekt_2** | Part Design tutorial, 3D views |
| **projekt_3** | Sketcher: `sketch_edit: true` in metafile, standard `run_metafile_test` |
| **projekt_4** | Assembly example, 3D views |
| **projekt_5** | TechDraw: 3D object + TechDraw page as separate images |

## Adding a new visual test project

**No Python file needed.** Add a new folder under `test/data/` with:

- **metafile.yaml** – model name, views, thresholds (see Metafile section above)
- **&lt;model&gt;.FCStd** – the FreeCAD file
- **references/** – created by `pixi run create-references-xvfb` or first run with `VISUAL_TEST_REFERENCE_MODE=create_missing`

The test runner (`test/test_visual_projects.py`) discovers every folder under `test/data/` that contains `metafile.yaml` and runs one test per folder.

**Sketcher (edit mode):** Set `sketch_edit: true` (and optionally `sketch_name`) on the view in the metafile – no extra code (e.g. projekt_3).

**Custom integration:** Use `discover_projects(data_dir)` for the list of project dirs; call `run_metafile_test(session, project_dir, reference_mode=...)`. Optional: `run_metafile_test(..., default_threshold=0.95)` to override the metafile threshold.

**Session:** The **freecad_vis_session** fixture (in `test/conftest.py`) provides a shared FreeCAD GUI session. Outside pytest: `from freecad.visual_tests.visual import VisualTestSession`; `session = VisualTestSession.start()`; then e.g. `run_metafile_test(session, path)`; `session.shutdown()` at the end.

## Known limitations

- **Platform:** Tested on Linux (pixi/conda). Without a visible desktop (e.g. CI), a virtual display is required (`pixi run test-xvfb`; needs xvfb and xauth installed).
- **One GUI session per run:** All tests share one FreeCAD GUI session (fixture); documents are opened and closed in sequence.
- **Order:** Test order can matter with shared documents or global FreeCAD settings.
- **One model per metafile:** Each `metafile.yaml` references exactly one `.FCStd` file; multiple models per metafile are not supported.
- **Shutdown:** On exit, `session.shutdown()` closes all open documents and processes Qt events. If FreeCAD segfaults after that, the wrapper script still returns the correct test exit code (from `.pytest_exitstatus`).

## Pixi tasks

| Task | Description |
|------|-------------|
| `pixi run test` | Run visual tests with pytest; `-s` shows SSIM metrics (requires display or xvfb) |
| `pixi run test-xvfb` | Run tests under xvfb (for CI/headless); exit code 0/1 reflects test result even if FreeCAD crashes on shutdown |
| `pixi run selftest` | Run SSIM/framework unit tests only (no FreeCAD GUI; fast) |
| `pixi run create-references-xvfb` | Create or update reference images (xvfb + `VISUAL_TEST_REFERENCE_MODE=update`) |
| `pixi run clean-artifacts` | Remove all files under `test/**/artifacts/*` |
| `pixi run clean-references` | Remove all files under `test/**/references/*` |
| `pixi run clean` | Remove both artifacts and references |
| `pixi run dev-install` | Install package in development mode (`pip install -e .`) |
| `pixi run build-pypi` | Build sdist and wheel for PyPI (output in `dist/`) |
| `pixi run upload-pypi` | Upload `dist/*` to PyPI (uses `TWINE_USERNAME`/`TWINE_PASSWORD` or `~/.pypirc`) |

## API (overview)

### Public API (for normal tests)

- **discover_projects(data_dir)**  
  Returns a sorted list of directories under **data_dir** that contain `metafile.yaml`. Used by the default test runner to find all projects.

- **run_metafile_test(session, metafile_path, reference_mode=None, default_threshold=None)**  
  Convenience function for most cases. **metafile_path** can be a folder (then `metafile.yaml`) or a file path. If **reference_mode** is `None`, uses env `VISUAL_TEST_REFERENCE_MODE` (default: `create_missing`). Opens the model, runs all views, compares with references.

- **VisualTestCase(session, metafile_path)**  
  Built from a `metafile.yaml`.  
  `run(reference_mode=..., default_threshold=...)` – open model, run views, close model.  
  `run_views_only(...)` – views only (document must already be open; for custom flow).

- **VisualTestSession** (from `freecad.visual_tests.visual`)  
  `start()`, `shutdown()`, `open_document`, `close_document`, `get_env_snapshot`. Provided in pytest via the **freecad_vis_session** fixture.

- **__version__** – Package version (e.g. `"0.1.0"`).

### SSIM module (no FreeCAD)

- **freecad.visual_tests.ssim** – `ComparisonResult`, `ssim_value(ref_arr, cand_arr)`, `compare_images_ssim(ref_path, cand_path, threshold, diff_output_path=None)`. Use for tests or tooling that must not import FreeCAD.

### Feature similarity (no FreeCAD, requires opencv)

- **freecad.visual_tests.similarity.feature_similarity(ref_path, cand_path, max_size=800)** → float in [0, 1]. ORB-based; robust to small perspective/scale/rotation. Use when the same content may appear with slightly different viewpoint (e.g. cross-system comparison).

### Advanced use / helpers

- **helper** (freecad.visual_tests.helper) – Sketcher and TechDraw control if you implement the flow yourself:  
  `set_sketch_edit_mode(enter, sketch_name=None)`, `set_active_techdraw_page(page_name=None)`, `unset_techdraw_page()`, `process_events_and_delay()`, and others.  
  Via the session: `session.set_sketch_edit_mode`, `session.set_active_techdraw_page`, `session.unset_techdraw_page`.

## Publishing to PyPI

- **Build:** `pixi run build-pypi` (creates `dist/`).
- **Upload (local):** `pixi run upload-pypi` (uses `TWINE_USERNAME` / `TWINE_PASSWORD` or `~/.pypirc`).
- **CI:** The workflow `.github/workflows/publish-pypi.yml` runs on **Release published** or **workflow_dispatch**. Add repository secret **PYPI_API_TOKEN** (create at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)), then create a release or run the workflow manually to publish.

## License / author

See `pyproject.toml` or project metadata.
