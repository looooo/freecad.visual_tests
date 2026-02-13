import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from freecad.visual_tests import VisualTestSession


@pytest.fixture(scope="session")
def freecad_vis_session():
    """One FreeCAD GUI session for the whole test run."""
    session = VisualTestSession.start()
    yield session
    session.shutdown()

