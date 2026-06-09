import importlib.util
import logging
import sys
import types
import unittest
from datetime import timezone
from unittest.mock import patch


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


if not has_module("zzupy.app"):
    zzupy_module = types.ModuleType("zzupy")
    zzupy_app_module = types.ModuleType("zzupy.app")
    zzupy_app_module.CASClient = object
    zzupy_app_module.ECardClient = object
    zzupy_module.app = zzupy_app_module
    sys.modules.setdefault("zzupy", zzupy_module)
    sys.modules.setdefault("zzupy.app", zzupy_app_module)


def retry(*args, **kwargs):
    def decorator(func):
        return func

    return decorator


def retry_factory(*args, **kwargs):
    return object()


if not has_module("tenacity"):
    tenacity_module = types.ModuleType("tenacity")
    tenacity_module.retry = retry
    tenacity_module.stop_after_attempt = retry_factory
    tenacity_module.wait_exponential = retry_factory
    tenacity_module.wait_chain = retry_factory
    tenacity_module.wait_fixed = retry_factory
    tenacity_module.retry_if_exception = retry_factory
    sys.modules.setdefault("tenacity", tenacity_module)

if not has_module("pytz"):
    pytz_module = types.ModuleType("pytz")
    pytz_module.timezone = lambda name: timezone.utc
    sys.modules.setdefault("pytz", pytz_module)

import crypto
import mfa
from monitor import EnergyMonitor, MFARequiredError, should_retry_exception


class FakeMFA:
    def __init__(self, required):
        self.required = required
        self.checked = False

    def is_required(self):
        self.checked = True
        return self.required


class FakeCASClient:
    def __init__(self, mfa_required=False):
        self.mfa = FakeMFA(mfa_required)
        self.device_ids = []

    def set_device(self, device_id):
        self.device_ids.append(device_id)


class FailingTokenCASClient(FakeCASClient):
    def __init__(self):
        super().__init__(mfa_required=False)
        self.logged_in = False
        self.user_token = None
        self.refresh_token = None
        self.tokens = None
        self.login_calls = 0

    def set_token(self, user_token, refresh_token):
        self.tokens = (user_token, refresh_token)

    def login(self):
        self.login_calls += 1
        raise RuntimeError("token expired")


class RetryingTokenCASClient(FailingTokenCASClient):
    def __init__(self):
        super().__init__()
        self.mfa.state = ""
        self.login_calls = 0

    def login(self):
        self.login_calls += 1
        if self.login_calls == 1:
            self.mfa.state = "detected-safe-device"
            self.mfa.required = False
            raise RuntimeError("mfa state required before token validation")

        self.logged_in = True
        self.user_token, self.refresh_token = self.tokens


class SuccessfulTokenCASClient(FailingTokenCASClient):
    def login(self):
        self.login_calls += 1
        self.logged_in = True
        self.user_token, self.refresh_token = self.tokens


class BootstrapMFA:
    def __init__(self, required):
        self.required = required
        self.sms_sent = False
        self.verified_code = None

    def is_required(self):
        return self.required

    def send_sms(self):
        self.sms_sent = True

    def verify_sms(self, code):
        self.verified_code = code


class BootstrapCASClient:
    def __init__(self, account, password, *, mfa_required=False):
        self.account = account
        self.password = password
        self.mfa = BootstrapMFA(mfa_required)
        self.device_ids = []
        self.login_called = False
        self.closed = False
        self.logged_in = False
        self.user_token = None
        self.refresh_token = None

    def set_device(self, device_id):
        self.device_ids.append(device_id)

    def login(self):
        self.login_called = True
        self.logged_in = True
        self.user_token = "new-user-token"
        self.refresh_token = "new-refresh-token"

    def close(self):
        self.closed = True


class AuthFlowTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def make_monitor(self, *, device_id=None, mfa_required=False):
        monitor = EnergyMonitor.__new__(EnergyMonitor)
        monitor.device_id = device_id
        monitor.cas_client = FakeCASClient(mfa_required=mfa_required)
        return monitor

    def test_mfa_required_error_is_not_retryable(self):
        self.assertFalse(should_retry_exception(MFARequiredError("mfa required")))
        self.assertTrue(should_retry_exception(RuntimeError("temporary failure")))

    def test_ensure_mfa_ready_raises_when_sms_is_required(self):
        monitor = self.make_monitor(mfa_required=True)

        with self.assertRaises(MFARequiredError):
            monitor._ensure_mfa_ready()

    def test_apply_device_reuses_saved_device_id_when_env_is_absent(self):
        monitor = self.make_monitor(device_id=None)

        monitor._apply_device({"device_id": "saved-device"})

        self.assertEqual(monitor.cas_client.device_ids, ["saved-device"])

    def test_apply_device_prefers_configured_device_id_over_saved_value(self):
        monitor = self.make_monitor(device_id="configured-device")

        monitor._apply_device({"device_id": "saved-device"})

        self.assertEqual(monitor.cas_client.device_ids, ["configured-device"])

    def test_saved_token_failure_does_not_precheck_mfa_state(self):
        monitor = self.make_monitor()
        monitor.cas_client = FailingTokenCASClient()

        ok = monitor._login_with_saved_token({
            "user_token": "old-user-token",
            "refresh_token": "old-refresh-token",
        })

        self.assertFalse(ok)
        self.assertEqual(
            monitor.cas_client.tokens,
            ("old-user-token", "old-refresh-token"),
        )
        self.assertFalse(monitor.cas_client.mfa.checked)

    def test_saved_token_login_can_reuse_token_when_mfa_is_required(self):
        monitor = self.make_monitor()
        monitor.cas_client = SuccessfulTokenCASClient()
        monitor.cas_client.mfa.required = True

        ok = monitor._login_with_saved_token({
            "user_token": "saved-user-token",
            "refresh_token": "saved-refresh-token",
        })

        self.assertTrue(ok)
        self.assertEqual(monitor.cas_client.login_calls, 1)
        self.assertEqual(
            monitor.cas_client.tokens,
            ("saved-user-token", "saved-refresh-token"),
        )

    def test_saved_token_login_retries_after_mfa_state_detection(self):
        monitor = self.make_monitor()
        monitor.cas_client = RetryingTokenCASClient()

        ok = monitor._login_with_saved_token({
            "user_token": "saved-user-token",
            "refresh_token": "saved-refresh-token",
        })

        self.assertTrue(ok)
        self.assertEqual(monitor.cas_client.login_calls, 2)
        self.assertFalse(monitor.cas_client.mfa.checked)
        self.assertEqual(
            monitor.cas_client.tokens,
            ("saved-user-token", "saved-refresh-token"),
        )

    def test_save_current_token_skips_incomplete_token(self):
        monitor = self.make_monitor()
        monitor.cas_client.user_token = "user-token"
        monitor.cas_client.refresh_token = None

        with patch("monitor.tokens.save") as save:
            monitor._save_current_token()

        save.assert_not_called()

    def test_crypto_requires_password(self):
        with patch.object(crypto, "PASSWORD", None):
            with self.assertRaises(SystemExit) as exit_context:
                with patch.object(sys, "argv", ["crypto.py", "encrypt"]):
                    with patch("builtins.print"):
                        crypto.main()

        self.assertEqual(exit_context.exception.code, 1)

    def test_mfa_bootstrap_sends_sms_and_saves_token_when_required(self):
        fake_client = BootstrapCASClient("student-id", "password", mfa_required=True)

        with patch.object(mfa, "ACCOUNT", "student-id"):
            with patch.object(mfa, "PASSWORD", "password"):
                with patch.object(mfa, "ZZU_DEVICE_ID", "trusted-device"):
                    with patch.object(mfa, "get_missing_required_env", return_value=[]):
                        with patch.object(mfa, "CASClient", return_value=fake_client):
                            with patch("builtins.input", return_value="123456"):
                                with patch.object(mfa.tokens, "save") as save:
                                    exit_code = mfa.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_client.device_ids, ["trusted-device"])
        self.assertTrue(fake_client.mfa.sms_sent)
        self.assertEqual(fake_client.mfa.verified_code, "123456")
        self.assertTrue(fake_client.login_called)
        self.assertTrue(fake_client.closed)
        save.assert_called_once_with("new-user-token", "new-refresh-token", "trusted-device")

    def test_mfa_bootstrap_rejects_empty_sms_code(self):
        fake_client = BootstrapCASClient("student-id", "password", mfa_required=True)

        with patch.object(mfa, "ACCOUNT", "student-id"):
            with patch.object(mfa, "PASSWORD", "password"):
                with patch.object(mfa, "ZZU_DEVICE_ID", None):
                    with patch.object(mfa, "get_missing_required_env", return_value=[]):
                        with patch.object(mfa, "CASClient", return_value=fake_client):
                            with patch("builtins.input", return_value=" "):
                                with patch.object(mfa.tokens, "save") as save:
                                    exit_code = mfa.main()

        self.assertEqual(exit_code, 1)
        self.assertTrue(fake_client.mfa.sms_sent)
        self.assertIsNone(fake_client.mfa.verified_code)
        self.assertFalse(fake_client.login_called)
        self.assertTrue(fake_client.closed)
        save.assert_not_called()

    def test_mfa_bootstrap_saves_token_without_sms_when_device_is_trusted(self):
        fake_client = BootstrapCASClient("student-id", "password", mfa_required=False)

        with patch.object(mfa, "ACCOUNT", "student-id"):
            with patch.object(mfa, "PASSWORD", "password"):
                with patch.object(mfa, "ZZU_DEVICE_ID", None):
                    with patch.object(mfa, "get_missing_required_env", return_value=[]):
                        with patch.object(mfa, "CASClient", return_value=fake_client):
                            with patch.object(mfa.tokens, "save") as save:
                                exit_code = mfa.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_client.device_ids, [])
        self.assertFalse(fake_client.mfa.sms_sent)
        self.assertIsNone(fake_client.mfa.verified_code)
        self.assertTrue(fake_client.login_called)
        self.assertTrue(fake_client.closed)
        save.assert_called_once_with("new-user-token", "new-refresh-token", None)


if __name__ == "__main__":
    unittest.main()
