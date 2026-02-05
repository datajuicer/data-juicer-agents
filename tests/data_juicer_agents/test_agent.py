import unittest
import asyncio
import os
import json
import tempfile
import shutil


class TestAgent(unittest.TestCase):
    """Test agent functionality with real API calls."""

    @classmethod
    def setUpClass(cls):
        """Check prerequisites before running tests."""
        if not os.environ.get("DASHSCOPE_API_KEY"):
            raise unittest.SkipTest(
                "DASHSCOPE_API_KEY not set. Please set it to run these tests."
            )
        # Create a temporary directory for test outputs
        cls.test_dir = tempfile.mkdtemp(prefix="dj_agent_test_")
        cls.test_data_path = os.path.join(cls.test_dir, "test_input.jsonl")
        cls.test_output_path = os.path.join(cls.test_dir, "test_output.jsonl")
        cls.test_config_path = os.path.join(cls.test_dir, "test_config.yaml")

        # Create test input data
        test_samples = [
            {"text": "This is a short text."},
            {"text": "This is a medium length text that has more words in it."},
            {"text": "A"},  # Very short, should be filtered out
            {"text": "This is another normal text sample for testing purposes."},
            {"text": ""},  # Empty, should be filtered out
        ]
        with open(cls.test_data_path, "w", encoding="utf-8") as f:
            for sample in test_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary directory."""
        if hasattr(cls, "test_dir") and os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def _run_async(self, coro):
        """Helper to run async functions."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _get_text_from_result(self, result):
        """Extract text from ToolResponse."""
        content = result.content[0]
        if hasattr(content, "text"):
            return content.text
        return content.get("text", str(content))

    # ==================== Basic Component Tests ====================

    def test_dj_toolkit_creation(self):
        """Test that DJ toolkit can be created."""
        from data_juicer_agents.tools import dj_toolkit

        self.assertIsNotNone(dj_toolkit)
        self.assertIsNotNone(dj_toolkit.tools)
        self.assertGreater(len(dj_toolkit.tools), 0)

    def test_dj_dev_toolkit_creation(self):
        """Test that DJ dev toolkit can be created."""
        from data_juicer_agents.tools import dj_dev_toolkit

        self.assertIsNotNone(dj_dev_toolkit)
        self.assertIsNotNone(dj_dev_toolkit.tools)
        self.assertGreater(len(dj_dev_toolkit.tools), 0)

    def test_prompts_not_empty(self):
        """Test that system prompts are properly defined."""
        from data_juicer_agents.core import (
            DJ_SYS_PROMPT,
            DJ_DEV_SYS_PROMPT,
            ROUTER_SYS_PROMPT,
        )

        self.assertGreater(len(DJ_SYS_PROMPT), 100)
        self.assertGreater(len(DJ_DEV_SYS_PROMPT), 100)
        self.assertGreater(len(ROUTER_SYS_PROMPT), 100)

    # ==================== Tool Function Tests ====================

    def test_get_ops_signature(self):
        """Test getting operator signatures."""
        from data_juicer_agents.tools.dj_helpers import get_ops_signature

        async def run():
            result = await get_ops_signature(["text_length_filter"])
            self.assertIsNotNone(result)
            text = self._get_text_from_result(result)
            self.assertIn("text_length_filter", text.lower())

        self._run_async(run())

    def test_execute_safe_command_allowed(self):
        """Test that allowed commands can be executed."""
        from data_juicer_agents.tools.dj_helpers import execute_safe_command

        async def run():
            result = await execute_safe_command("echo hello")
            text = self._get_text_from_result(result)
            self.assertIn("<returncode>0</returncode>", text)
            self.assertIn("hello", text)

        self._run_async(run())

    def test_execute_safe_command_blocked(self):
        """Test that dangerous commands are blocked."""
        from data_juicer_agents.tools.dj_helpers import execute_safe_command

        async def run():
            result = await execute_safe_command("curl http://example.com")
            text = self._get_text_from_result(result)
            self.assertIn("<returncode>-1</returncode>", text)
            self.assertIn("not allowed", text)

        self._run_async(run())

if __name__ == "__main__":
    unittest.main()
