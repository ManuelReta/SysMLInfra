import sys
import pytest
from unittest.mock import patch

from sys_infra.entry import create_parser, main


def test_check_command_parsing():
    parser = create_parser()
    args = parser.parse_args(
        ["check", "file1.sysml", "--fallback", "--expect-violations"]
    )

    assert args.command == "check"
    assert args.targets == ["file1.sysml"]
    assert args.fallback is True
    assert args.expect_violations is True


def test_verify_command_parsing():
    parser = create_parser()
    args = parser.parse_args(["verify", "--dry-run", "--visual", "--z3"])

    assert args.command == "verify"
    assert args.dry_run is True
    assert args.visual is True
    assert args.z3 is True


def test_sensor_defaults():
    parser = create_parser()
    args = parser.parse_args(["sensor"])

    assert args.interval == 5.0
    assert args.output == "pretty"


def test_eval_flags():
    parser = create_parser()
    args = parser.parse_args(["eval", "--negative", "--raw"])

    assert args.negative is True
    assert args.raw is True


@patch("sys_infra.entry.run_check")
def test_main_dispatch_check(mock_run_check):
    test_argv = ["prog", "check", "a.sysml"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_check.assert_called_once()
    kwargs = mock_run_check.call_args.kwargs
    assert kwargs["targets"] == ["a.sysml"]


@patch("sys_infra.entry.run_verify")
def test_main_dispatch_verify(mock_run_verify):
    test_argv = ["prog", "verify", "--dry-run", "--published"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_verify.assert_called_once()
    kwargs = mock_run_verify.call_args.kwargs
    assert kwargs["dry_run"] is True
    assert kwargs["published"] is True


@patch("sys_infra.entry.run_sensor")
def test_main_dispatch_sensor(mock_run_sensor):
    test_argv = ["prog", "sensor", "--once", "--interval", "1.5"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_sensor.assert_called_once()
    kwargs = mock_run_sensor.call_args.kwargs
    assert kwargs["once"] is True
    assert kwargs["interval"] == 1.5


@patch("sys_infra.entry.run_validate")
def test_main_dispatch_validate(mock_run_validate):
    test_argv = ["prog", "validate", "--dry-run"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_validate.assert_called_once()
    kwargs = mock_run_validate.call_args.kwargs
    assert kwargs["dry_run"] is True


@patch("sys_infra.entry.run_trace")
def test_main_dispatch_trace(mock_run_trace):
    test_argv = ["prog", "trace", "--dry-run"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_trace.assert_called_once()
    kwargs = mock_run_trace.call_args.kwargs
    assert kwargs["dry_run"] is True


@patch("sys_infra.entry.run_eval")
def test_main_dispatch_eval(mock_run_eval):
    test_argv = ["prog", "eval", "--negative"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_run_eval.assert_called_once()
    kwargs = mock_run_eval.call_args.kwargs
    assert kwargs["negative"] is True


def test_unknown_command_exits():
    parser = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])  # required command missing
