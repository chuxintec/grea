import contextlib
import io
import json
from unittest.mock import patch
from grea.recovery.cli import main


def test_native_recovery_cli_forwards_pinned_inputs_and_reports_receipt_only():
    result = {"status": "recovery_receipt_created", "nativeExitCode": None,
              "verification": "failed_before_report", "report": "fresh/recovery.json"}
    stdout = io.StringIO()
    with patch("grea.recovery.native.recover_execution", return_value=result) as recover, contextlib.redirect_stdout(stdout):
        assert main(["recover-native-execution", "--request", "request.json",
                     "--expected-request", "a" * 64, "--out", "fresh"]) == 0
    assert json.loads(stdout.getvalue()) == result
    recover.assert_called_once_with("request.json", "a" * 64, "fresh")


def test_native_recovery_cli_is_discoverable():
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert main(["capabilities", "--json"]) == 0
    assert "recover-native-execution" in json.loads(stdout.getvalue())["implemented"]
