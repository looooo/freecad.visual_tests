import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from freecad.visual_tests.visual import VisualTestSession


@pytest.fixture(scope="session")
def freecad_vis_session(request):
    """One FreeCAD GUI session for the whole test run."""
    session = VisualTestSession.start()
    yield session
    try:
        status = 0 if request.node.session.testsfailed == 0 else 1
        _write_exitstatus(status)
    except Exception:
        pass
    session.shutdown()


def _write_exitstatus(value: int) -> None:
    try:
        (PROJECT_ROOT / ".pytest_exitstatus").write_text(str(value))
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    """Backup: persist exit status in case wrapper needs it after abnormal exit."""
    _write_exitstatus(exitstatus)

