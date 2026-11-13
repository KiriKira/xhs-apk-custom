#!/usr/bin/env python3
"""Run tools/verify_rednote_release.py with the repo's tools package winning.

This container ships its own ``tools`` package on sys.path, which shadows the
repository's ``tools/`` directory. Registering a namespace module for ``tools``
whose ``__path__`` points at the repo first lets the release verifier import
``tools.build_rednote_package_fix`` and sibling helpers as CI does.
"""

import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

if "tools" not in sys.modules or not hasattr(sys.modules["tools"], "__path__"):
    package = types.ModuleType("tools")
    package.__path__ = [str(REPO / "tools")]
    sys.modules["tools"] = package
else:
    sys.modules["tools"].__path__ = [str(REPO / "tools"), *list(sys.modules["tools"].__path__)]

# The verifier imports its siblings by bare module name (``verify_fold_dex`` etc.).
sys.argv = [str(REPO / "tools" / "verify_rednote_release.py"), *sys.argv[1:]]
exec(compile((REPO / "tools" / "verify_rednote_release.py").read_text(), "verify_rednote_release.py", "exec"),
     {"__name__": "__main__", "__file__": str(REPO / "tools" / "verify_rednote_release.py")})
