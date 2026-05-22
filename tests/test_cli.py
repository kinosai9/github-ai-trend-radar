import pytest

from github_ai_trend_radar.main import main


def test_help_runs(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "Generate GitHub AI open source trend reports" in capsys.readouterr().out


def test_render_requires_scored_snapshot(tmp_path, capsys):
    exit_code = main(["render", "--period", "weekly", "--snapshot-dir", str(tmp_path)])

    assert exit_code == 1
    assert "No scored snapshot found" in capsys.readouterr().out


def test_help_lists_doctor(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


def test_collect_defaults_allow_empty_and_do_not_fail_fast():
    parser = __import__("github_ai_trend_radar.main", fromlist=["build_parser"]).build_parser()

    args = parser.parse_args(["collect"])

    assert args.fail_fast is False
    assert args.allow_empty is True


def test_run_supports_collect_failure_flags():
    parser = __import__("github_ai_trend_radar.main", fromlist=["build_parser"]).build_parser()

    args = parser.parse_args(["run", "--fail-fast", "--no-allow-empty"])

    assert args.fail_fast is True
    assert args.allow_empty is False
