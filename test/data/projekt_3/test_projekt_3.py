"""Sketcher test: sketch_edit in metafile, standard run_metafile_test."""
from pathlib import Path

from freecad.visual_tests import run_metafile_test

BASE_DIR = Path(__file__).resolve().parent


def test_projekt_3_sketcher(freecad_vis_session):
    run_metafile_test(
        freecad_vis_session,
        BASE_DIR,
        reference_mode="create_missing",
    )
