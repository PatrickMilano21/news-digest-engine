from src.weekly_report import write_weekly_report



def test_weekly_report_creates_file(tmp_path, monkeypatch):
    test_output = tmp_path / "artifacts" / "weekly_report.md"
    monkeypatch.setattr("src.weekly_report.WEEKLY_REPORT_PATH", test_output)

    result = write_weekly_report(conn=None, end_day="2026-01-20", days=7)

    assert test_output.exists()
    assert result == str(test_output)


def test_weekly_report_header_contains_date_range(tmp_path, monkeypatch):
    test_output = tmp_path / "artifacts" / "weekly_report.md"
    monkeypatch.setattr("src.weekly_report.WEEKLY_REPORT_PATH", test_output)

    write_weekly_report(conn=None, end_day="2026-01-20", days=7)

    content = test_output.read_text()
    assert "2026-01-14" in content  # start_day
    assert "2026-01-20" in content  # end_day


def test_weekly_report_has_all_sections(tmp_path, monkeypatch):
    test_output = tmp_path / "artifacts" / "weekly_report.md"
    monkeypatch.setattr("src.weekly_report.WEEKLY_REPORT_PATH", test_output)

    write_weekly_report(conn=None, end_day="2026-01-20", days=7)

    content = test_output.read_text()
    assert "## Top Sources" in content
    assert "## Boost Config" in content
    assert "## Eval Pass Rate" in content
    assert "## Run Failures" in content