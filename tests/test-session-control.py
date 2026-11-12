#!/usr/bin/env python3
"""Idle policy and fail-closed sleep ordering. Never contacts X11/system bus."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana"))
from session_control import IdlePolicy, suspend


class SessionPolicy(unittest.TestCase):
    def test_once_per_idle_period_and_live_policy_changes(self):
        policy = IdlePolicy()
        self.assertFalse(policy.due(1_000_000, 0))
        self.assertFalse(policy.due(59_999, 1))
        self.assertTrue(policy.due(60_000, 1))
        self.assertFalse(policy.due(120_000, 1))
        self.assertFalse(policy.due(10, 1))
        self.assertTrue(policy.due(60_000, 1))
        self.assertFalse(policy.due(60_000, 10))
        self.assertTrue(policy.due(600_000, 10))
        self.assertFalse(policy.due(600_000, 0))

    def test_provider_denial_never_locks_or_sleeps(self):
        for state in ("no", "na", "challenge", "inhibited", "inhibitor-blocked", "challenge-inhibitor-blocked", "unavailable", "unknown"):
            events = []
            class Manager:
                def can_suspend(self): events.append("check"); return state
                def suspend(self): events.append("sleep")
            rc, _ = suspend(Manager(), lambda: (events.append("lock") or (0, "")))
            self.assertNotEqual(rc, 0)
            self.assertEqual(events, ["check"])

    def test_lock_failure_and_lost_permission_keep_machine_awake(self):
        events = []
        class Manager:
            def can_suspend(self): events.append("check"); return "yes"
            def suspend(self): events.append("sleep")
        self.assertNotEqual(suspend(Manager(), lambda: (events.append("lock") or (3, "No usable password")))[0], 0)
        self.assertEqual(events, ["check", "lock"])
        events.clear()
        class Changed(Manager):
            def can_suspend(self): events.append("check"); return "yes" if len(events) == 1 else "no"
        self.assertNotEqual(suspend(Changed(), lambda: (events.append("lock") or (0, "")))[0], 0)
        self.assertEqual(events, ["check", "lock", "check"])

    def test_sleep_only_after_ready_lock_and_fresh_permission(self):
        events = []
        class Manager:
            def can_suspend(self): events.append("check"); return "yes"
            def suspend(self): events.append("sleep")
        rc, _ = suspend(Manager(), lambda: (events.append("lock") or (0, "")))
        self.assertEqual(rc, 0)
        self.assertEqual(events, ["check", "lock", "check", "sleep"])


if __name__ == "__main__":
    unittest.main()
