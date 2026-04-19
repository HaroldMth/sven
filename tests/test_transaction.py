# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_transaction.py — tests for Phase 6
# ============================================================

import unittest
from unittest.mock import patch, MagicMock

from sven.transaction import Transaction, InstallTransaction, RemoveTransaction


class TestTransaction(unittest.TestCase):

    def setUp(self):
        self.cfg_patch = patch("sven.transaction.get_config")
        self.mock_cfg_func = self.cfg_patch.start()
        self.mock_config = MagicMock()
        self.mock_config.rooted.side_effect = lambda p: f"/tmp/sven_test{p}"
        self.mock_cfg_func.return_value = self.mock_config
        
        self.db_patch = patch("sven.transaction.LocalDB")
        self.mock_db_class = self.db_patch.start()
        self.mock_db = MagicMock()
        self.mock_db.acquire_lock.return_value = True
        self.mock_db_class.return_value = self.mock_db
        
        self.rb_patch = patch("sven.transaction.RollbackManager")
        self.mock_rollback_class = self.rb_patch.start()
        self.mock_rollback = MagicMock()
        self.mock_rollback.create_snapshot.return_value = "snap-123"
        self.mock_rollback_class.return_value = self.mock_rollback

    def tearDown(self):
        self.db_patch.stop()
        self.rb_patch.stop()
        self.cfg_patch.stop()

    def test_transaction_lock_failure(self):
        """Should fail immediately if lock cannot be acquired."""
        self.mock_db.acquire_lock.return_value = False
        tx = Transaction()
        success = tx.execute(["foo"])
        
        self.assertFalse(success)
        self.mock_rollback.create_snapshot.assert_not_called()

    def test_transaction_rollback_on_error(self):
        """Should trigger rollback if internal operation raises Exception."""
        tx = Transaction()
        
        class FaultyTx(Transaction):
            def _execute_core(self, pkgs, **kwargs):
                raise ValueError("Oops!")

        faulty = FaultyTx()
        success = faulty.execute(["bar"])
        
        self.assertFalse(success)
        # Should have captured the snapshot and restored it
        self.mock_rollback.create_snapshot.assert_called_once()
        self.mock_rollback.restore.assert_called_once_with("snap-123")

    def test_transaction_success(self):
        """Should release lock and log on success."""
        class GoodTx(Transaction):
            def _execute_core(self, pkgs, **kwargs):
                return True

        tx = GoodTx()
        success = tx.execute(["bar"])
        
        self.assertTrue(success)
        self.mock_rollback.create_snapshot.assert_called_once()
        self.mock_rollback.restore.assert_not_called()
        self.mock_db.release_lock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
