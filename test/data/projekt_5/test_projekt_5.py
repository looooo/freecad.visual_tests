import os
from pathlib import Path

from freecad.visual_tests import run_metafile_test

BASE_DIR = Path(__file__).resolve().parent
REFERENCE_MODE = os.environ.get("VISUAL_TEST_REFERENCE_MODE", "create_missing")


def test_projekt_5_techdraw(freecad_vis_session):
    run_metafile_test(
        freecad_vis_session,
        BASE_DIR,
        reference_mode=REFERENCE_MODE,
    )
