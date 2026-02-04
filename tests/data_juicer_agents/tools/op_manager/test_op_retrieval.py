import unittest
import asyncio
import os


class TestOpRetrieval(unittest.TestCase):
    """Test operator retrieval with real API calls."""

    @classmethod
    def setUpClass(cls):
        """Check prerequisites before running tests."""
        if not os.environ.get("DASHSCOPE_API_KEY"):
            raise unittest.SkipTest(
                "DASHSCOPE_API_KEY not set. Please set it to run these tests."
            )

    def _run_async(self, coro):
        """Helper to run async functions."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_init_dj_func_info(self):
        """Test that dj_func_info can be initialized."""
        from data_juicer_agents.tools.op_manager.op_retrieval import (
            init_dj_func_info,
            get_dj_func_info,
        )

        result = init_dj_func_info()
        self.assertTrue(result)

        func_info = get_dj_func_info()
        self.assertIsInstance(func_info, list)
        self.assertGreater(len(func_info), 100)
        # Each operator should have class_name and class_desc
        for op in func_info[:3]:
            self.assertIn("class_name", op)
            self.assertIn("class_desc", op)
            self.assertIn("arguments", op)

    def test_retrieve_text_filter_operators_with_llm(self):
        """Test retrieving text filtering operators using LLM."""
        from data_juicer_agents.tools.op_manager.op_retrieval import retrieve_ops

        async def run():
            results = await retrieve_ops("filter text by length", limit=5, mode="llm")
            # Results could be a list
            self.assertIsInstance(results, list)
            first_result = results[0]
            self.assertEqual("text_length_filter", first_result)

        self._run_async(run())
    
    def test_retrieve_text_filter_operators_with_vector(self):
        """Test retrieving text filtering operators using vector."""
        from data_juicer_agents.tools.op_manager.op_retrieval import retrieve_ops
        async def run():
            results = await retrieve_ops("filter text by length", limit=5, mode="vector")
            # Results could be a list
            self.assertIsInstance(results, list)
            first_result = results[0]
            self.assertEqual("text_length_filter", first_result)
        
        self._run_async(run())

    def test_get_content_hash_consistency(self):
        """Test _get_content_hash produces consistent hashes."""
        from data_juicer_agents.tools.op_manager.op_retrieval import _get_content_hash

        data = [{"name": "op1"}, {"name": "op2"}]
        hash1 = _get_content_hash(data)
        hash2 = _get_content_hash(data)

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 produces 64 hex chars


if __name__ == "__main__":
    unittest.main()
