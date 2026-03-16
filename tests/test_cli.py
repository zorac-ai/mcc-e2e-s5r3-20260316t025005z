from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(db_path: Path, *args: str) -> object:
    result = subprocess.run(
        [sys.executable, "-m", "issue_tracker", "--db", str(db_path), *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "issues.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_json(self, *args: str) -> object:
        return run_cli(self.db_path, *args)

    def test_create_and_list_open_issues(self) -> None:
        created = self.run_json("add", "Ship the CLI")
        self.assertEqual(created["id"], 1)
        self.assertEqual(created["status"], "open")

        issues = self.run_json("list")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "Ship the CLI")

    def test_list_includes_created_issue(self) -> None:
        created = self.run_json("add", "Document the commands")
        issues = self.run_json("list")
        self.assertEqual(issues[0]["id"], created["id"])
        self.assertEqual(issues[0]["title"], "Document the commands")

    def test_close_issue_and_filter_closed(self) -> None:
        self.run_json("add", "Close me")
        closed = self.run_json("close", "1")
        self.assertEqual(closed["status"], "closed")
        self.assertIsNotNone(closed["closed_at"])

        issues = self.run_json("list", "--status", "closed")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["id"], 1)

    def test_missing_issue_returns_non_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "issue_tracker", "--db", str(self.db_path), "close", "999"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("issue 999 not found", result.stderr)


class ImportCsvTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "issues.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_csv(self, name: str, rows: list[dict]) -> Path:
        csv_path = Path(self.temp_dir.name) / name
        fieldnames = list(rows[0].keys()) if rows else ["title"]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return csv_path

    def test_import_csv_creates_issues(self) -> None:
        import csv as _csv
        csv_path = Path(self.temp_dir.name) / "import.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["title"])
            writer.writeheader()
            writer.writerow({"title": "First issue"})
            writer.writerow({"title": "Second issue"})

        created = run_cli(self.db_path, "import", str(csv_path))
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0]["title"], "First issue")
        self.assertEqual(created[0]["status"], "open")
        self.assertEqual(created[1]["title"], "Second issue")
        self.assertEqual(created[1]["id"], 2)

    def test_import_csv_persists_to_store(self) -> None:
        import csv as _csv
        csv_path = Path(self.temp_dir.name) / "import.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["title"])
            writer.writeheader()
            writer.writerow({"title": "Persisted issue"})

        run_cli(self.db_path, "import", str(csv_path))
        issues = run_cli(self.db_path, "list")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "Persisted issue")

    def test_import_csv_missing_title_column_fails(self) -> None:
        import csv as _csv
        csv_path = Path(self.temp_dir.name) / "bad.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["summary"])
            writer.writeheader()
            writer.writerow({"summary": "No title column"})

        result = subprocess.run(
            [sys.executable, "-m", "issue_tracker", "--db", str(self.db_path), "import", str(csv_path)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_import_csv_empty_file_returns_empty_list(self) -> None:
        import csv as _csv
        csv_path = Path(self.temp_dir.name) / "empty.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["title"])
            writer.writeheader()

        created = run_cli(self.db_path, "import", str(csv_path))
        self.assertEqual(created, [])

    def test_import_csv_extra_columns_ignored(self) -> None:
        import csv as _csv
        csv_path = Path(self.temp_dir.name) / "extra.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=["title", "priority"])
            writer.writeheader()
            writer.writerow({"title": "Extra cols issue", "priority": "high"})

        created = run_cli(self.db_path, "import", str(csv_path))
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["title"], "Extra cols issue")


if __name__ == "__main__":
    unittest.main()
