"""Exercise standalone audit startup with the real shared logging adapter."""

import csv
import subprocess
import sys
from pathlib import Path


def testEmptyAuditReportsDryRunWithSharedLogging(tmp_path):
    source = tmp_path / "media"
    source.mkdir()
    report = tmp_path / "audit.csv"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "rugbyAudit.py"),
            "--source",
            str(source),
            "--outputCsv",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "files processed: 0" in result.stdout + result.stderr
    assert "mode: dry-run" in result.stdout + result.stderr
    with report.open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert "writeMode" in reader.fieldnames
        assert list(reader) == []
    assert list(source.iterdir()) == []
