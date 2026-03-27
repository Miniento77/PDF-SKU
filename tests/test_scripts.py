import subprocess
import unittest
from pathlib import Path


class ScriptTests(unittest.TestCase):
    def test_run_web_script_points_to_project_venv_python(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        script_path = project_root / "scripts" / "run_web.sh"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn('VENV_PY="$ROOT_DIR/.venv/bin/python"', content)
        self.assertIn('exec "$VENV_PY" app.py "$@"', content)


if __name__ == "__main__":
    unittest.main()
