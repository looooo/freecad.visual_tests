"""Visual tests driven by metafile.yaml only. No per-project Python files."""
from pathlib import Path

import pytest

from freecad.visual_tests import discover_projects, run_metafile_test

DATA_DIR = Path(__file__).resolve().parent / "data"
PROJECT_DIRS = discover_projects(DATA_DIR)


@pytest.mark.parametrize("project_dir", PROJECT_DIRS, ids=[d.name for d in PROJECT_DIRS])
def test_visual_project(freecad_vis_session, project_dir: Path):
    run_metafile_test(freecad_vis_session, project_dir)
