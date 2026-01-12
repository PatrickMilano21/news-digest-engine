import subprocess
import sys 

def test_run_rejects_invalid_date():
    result = subprocess.run(
        [sys.executable, "-m", "src.run", "--date", "not-a-date"],
        capture_output=True,
    )
    assert result.returncode != 0