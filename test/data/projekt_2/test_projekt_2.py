from pathlib import Path

from freecad.visual_tests import run_metafile_test

BASE_DIR = Path(__file__).resolve().parent


def test_projekt_2_basic_part(freecad_vis_session):
    run_metafile_test(
        freecad_vis_session,
        BASE_DIR,
        reference_mode="create_missing",
    )

