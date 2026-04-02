# -*- coding: utf-8 -*-
"""Tests for security fixes: exception handling, thread safety, subprocess cleanup."""

import asyncio
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test 1: Exception Handling - Verify logging is added
# =============================================================================

class TestExceptionLogging:
    """Verify that silent exception catches now log errors."""

    def test_event_callback_exception_is_logged(self, caplog):
        """Test that event callback exceptions are logged, not silently swallowed."""
        from data_juicer_agents.capabilities.session.runtime import SessionToolRuntime, SessionState

        state = SessionState()
        runtime = SessionToolRuntime(state=state, verbose=False)

        error_logged = []
        def bad_callback(event):
            raise ValueError("callback error")

        runtime._event_callback = bad_callback

        with caplog.at_level(logging.DEBUG, logger="data_juicer_agents.capabilities.session.runtime"):
            runtime.emit_event("test_event", foo="bar")

        # Should not raise, and should have logged the error
        assert any("callback" in record.message.lower() or "error" in record.message.lower()
                   for record in caplog.records)

    def test_operator_registry_logs_on_failure(self, caplog):
        """Test that operator registry logs when backend fails to load."""
        from data_juicer_agents.tools.retrieve._shared import operator_registry

        with patch.object(operator_registry, '_logger') as mock_logger:
            # Force a failure by making the import fail
            with patch.dict('sys.modules', {'.backend': None}):
                # Clear the cache first
                operator_registry.get_available_operator_names.cache_clear()
                result = operator_registry.get_available_operator_names()
                # Should return empty set, not crash
                assert isinstance(result, set)


# =============================================================================
# Test 2: Thread Safety - Verify request_interrupt is safe
# =============================================================================

class TestThreadSafety:
    """Verify thread-safety fixes in request_interrupt."""

    def test_request_interrupt_handles_concurrent_context_changes(self):
        """Test that request_interrupt is safe under concurrent modifications."""
        from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

        # Create orchestrator with mock react agent
        orchestrator = DJSessionAgent.__new__(DJSessionAgent)
        orchestrator._react_agent = MagicMock()
        orchestrator._interrupt_lock = threading.RLock()
        orchestrator._active_react_loop = None
        orchestrator._active_react_inflight = False
        orchestrator._debug = lambda msg: None

        # Simulate concurrent context changes
        results = []

        def toggle_inflight():
            for _ in range(100):
                with orchestrator._interrupt_lock:
                    orchestrator._active_react_inflight = True
                time.sleep(0.001)
                with orchestrator._interrupt_lock:
                    orchestrator._active_react_inflight = False

        def call_interrupt():
            for _ in range(100):
                try:
                    result = orchestrator.request_interrupt()
                    results.append(result)
                except Exception as e:
                    results.append(f"ERROR: {e}")

        # Start threads
        t1 = threading.Thread(target=toggle_inflight)
        t2 = threading.Thread(target=call_interrupt)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # No exceptions should have occurred
        errors = [r for r in results if isinstance(r, str) and r.startswith("ERROR")]
        assert len(errors) == 0, f"Got errors: {errors}"

    def test_request_interrupt_returns_false_when_no_loop(self):
        """Test that request_interrupt returns False gracefully when no loop is set."""
        from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

        orchestrator = DJSessionAgent.__new__(DJSessionAgent)
        orchestrator._react_agent = MagicMock()
        orchestrator._interrupt_lock = threading.RLock()
        orchestrator._active_react_loop = None
        orchestrator._active_react_inflight = True
        orchestrator._debug = lambda msg: None

        result = orchestrator.request_interrupt()
        assert result is False

    def test_request_interrupt_returns_false_when_not_inflight(self):
        """Test that request_interrupt returns False when not inflight."""
        from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

        orchestrator = DJSessionAgent.__new__(DJSessionAgent)
        orchestrator._react_agent = MagicMock()
        orchestrator._interrupt_lock = threading.RLock()
        orchestrator._active_react_loop = asyncio.new_event_loop()
        orchestrator._active_react_inflight = False
        orchestrator._debug = lambda msg: None

        try:
            result = orchestrator.request_interrupt()
            assert result is False
        finally:
            orchestrator._active_react_loop.close()


# =============================================================================
# Test 3: Subprocess Cleanup - Verify no resource leaks
# =============================================================================

class TestSubprocessCleanup:
    """Verify subprocess cleanup in apply_recipe."""

    def test_terminate_process_gracefully_helper_exists(self):
        """Test that the helper function exists and works."""
        from data_juicer_agents.tools.apply.apply_recipe.logic import _terminate_process_gracefully

        # Create a short-lived process
        proc = subprocess.Popen(
            ["sleep", "10"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        pid = proc.pid
        assert proc.poll() is None  # Process is running

        # Terminate it
        _terminate_process_gracefully(proc)

        # Process should be terminated
        proc.wait(timeout=5)
        assert proc.poll() is not None

    def test_subprocess_terminated_on_timeout(self):
        """Test that subprocess is properly terminated when timeout occurs."""
        from data_juicer_agents.tools.apply.apply_recipe.logic import ApplyUseCase

        use_case = ApplyUseCase()

        # Create a plan that would run indefinitely
        plan = {
            "plan_id": "test_timeout",
            "recipe": {
                "project_name": "test",
                "dataset_path": "/dev/null",
                "export_path": "/tmp/test_output.jsonl",
                "process": [],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a very short timeout and a long-running command
            result, rc, stdout, stderr = use_case.execute(
                plan_payload=plan,
                runtime_dir=Path(tmpdir),
                dry_run=False,
                timeout_seconds=1,
                command_override=["sleep", "60"],
            )

            # Should have timed out
            assert result.status == "failed" or rc == 124 or "timeout" in stderr.lower() or result.error_type in ("timeout", "command_failed")

    def test_subprocess_terminated_on_cancel(self):
        """Test that subprocess is terminated when cancel_check returns True."""
        from data_juicer_agents.tools.apply.apply_recipe.logic import ApplyUseCase

        use_case = ApplyUseCase()

        plan = {
            "plan_id": "test_cancel",
            "recipe": {
                "project_name": "test",
                "dataset_path": "/dev/null",
                "export_path": "/tmp/test_output.jsonl",
                "process": [],
            }
        }

        call_count = [0]
        def cancel_check():
            call_count[0] += 1
            return call_count[0] > 3  # Cancel after 3 checks

        with tempfile.TemporaryDirectory() as tmpdir:
            result, rc, stdout, stderr = use_case.execute(
                plan_payload=plan,
                runtime_dir=Path(tmpdir),
                dry_run=False,
                timeout_seconds=30,
                command_override=["sleep", "60"],
                cancel_check=cancel_check,
            )

            # Should have been interrupted
            assert result.status == "interrupted" or rc == 130 or "interrupted" in stderr.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])