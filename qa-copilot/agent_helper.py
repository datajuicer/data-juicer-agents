# -*- coding: utf-8 -*-
# Copyright 2025 Alibaba
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ==============================================================================
# This file contains code from alias
# Original repository: https://github.com/agentscope-ai/agentscope-samples/tree/main/alias
#
# Modifications made by data-juicer, 2026
# ==============================================================================
import os
import json
import asyncio
import time
import traceback
from loguru import logger
from typing import Optional, Any, List, Literal, Callable, Awaitable, Dict
from pydantic import BaseModel, Field

from agentscope.mcp import HttpStatelessClient
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.rag import SimpleKnowledge, QdrantStore
from agentscope.tool import Toolkit
from agentscope.session import JSONSession
from agentscope.memory import InMemoryMemory, RedisMemory
from agentscope.agent import AgentBase
from agentscope.message import Msg
from redis.asyncio import ConnectionPool

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from op_manager.dj_op_retriever import DJOperatorRetriever
from url_verifier.verify_urls import verify_urls


class SessionLockManager(object):
    def __init__(self):
        self._session_locks = {}
        self._lock_manager_lock = asyncio.Lock()

    async def get_session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._lock_manager_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

    async def cleanup_session_lock(self, session_id: str) -> None:
        async with self._lock_manager_lock:
            if session_id in self._session_locks:
                del self._session_locks[session_id]


class JSONSessionHistoryService(object):
    def __init__(self, session_store_type: str = "json"):
        self.session_store_type = session_store_type
        self.session = JSONSession(
            save_dir=os.getenv("SESSION_STORE_DIR", "./sessions")
        )

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def get_memory(
        self, session_id: str, user_id: Optional[str] = None
    ) -> List[Msg]:
        session_save_path = self.session._get_save_path(session_id, user_id)
        if not os.path.exists(session_save_path):
            logger.warning(f"session_save_path={session_save_path} not exists")
            return []
        try:
            with open(
                session_save_path,
                "r",
                encoding="utf-8",
                errors="surrogatepass",
            ) as file:
                memory_states = json.load(file)["agent"]["memory"]
                temp_memory = InMemoryMemory()
                temp_memory.load_state_dict(memory_states)
                memory = await temp_memory.get_memory()
                return memory
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                f"Failed to load or parse memory from {session_save_path}: {e}"
            )
            return []

    async def delete_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> None:
        session_save_path = self.session._get_save_path(session_id, user_id)
        if os.path.exists(session_save_path):
            os.remove(session_save_path)

    async def load_session_state(
        self,
        session_id: str,
        agent: AgentBase,
        user_id: Optional[str] = None,
    ) -> None:
        await self.session.load_session_state(
            session_id=session_id, agent=agent, user_id=user_id
        )

    async def save_session_state(
        self, session_id: str, agent: AgentBase, user_id: Optional[str] = None
    ) -> None:
        await self.session.save_session_state(
            session_id=session_id, agent=agent, user_id=user_id
        )

    def create_memory(self, user_id: str, session_id: str):
        """Create an InMemoryMemory instance for the agent."""
        # For JSON mode, create an empty InMemoryMemory instance
        # Load/save session state should be handled manually
        return InMemoryMemory()

    async def cleanup_memory(self, memory: Any) -> None:
        """Cleanup memory resources if needed."""
        # InMemoryMemory doesn't need cleanup
        pass


class RedisSessionHistoryService(object):
    """Redis-based session history service."""

    def __init__(
        self,
        session_store_type: str = "redis",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        redis_max_connections: int = 10,
    ):
        self.session_store_type = session_store_type
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._redis_db = redis_db
        self._redis_password = redis_password
        self._redis_max_connections = redis_max_connections
        self.connection_pool: Optional[ConnectionPool] = None

    async def start(self) -> None:
        """Initialize Redis connection pool."""
        self.connection_pool = ConnectionPool(
            host=self._redis_host,
            port=self._redis_port,
            db=self._redis_db,
            password=self._redis_password,
            decode_responses=True,
            max_connections=self._redis_max_connections,
            encoding="utf-8",
        )
        logger.info(
            f"✅ Initialized RedisConnectionPool with host: {self._redis_host}, port: {self._redis_port}, db: {self._redis_db}"
        )

    async def stop(self) -> None:
        """Close Redis connection pool."""
        if self.connection_pool:
            await self.connection_pool.disconnect()
            self.connection_pool = None

    def get_connection_pool(self) -> ConnectionPool:
        """Get the Redis connection pool."""
        if self.connection_pool is None:
            raise RuntimeError(
                "RedisSessionHistoryService not started. Call start() first."
            )
        return self.connection_pool

    def create_memory(self, user_id: str, session_id: str):
        """Create a RedisMemory instance for the agent."""
        return RedisMemory(
            connection_pool=self.get_connection_pool(),
            user_id=user_id,
            session_id=session_id,
        )

    async def cleanup_memory(self, memory: Any) -> None:
        """Cleanup memory resources if needed."""
        try:
            client = memory.get_client()
            await client.aclose()
        except Exception as e:
            logger.warning(f"Failed to cleanup memory: {e}")

    async def get_memory(
        self, session_id: str, user_id: Optional[str] = None
    ) -> List[Msg]:
        """Get memory content for a session."""
        memory = None
        try:
            memory = RedisMemory(
                connection_pool=self.get_connection_pool(),
                user_id=user_id or session_id,
                session_id=session_id,
            )
            memory_content = await memory.get_memory()
            return memory_content
        except Exception as e:
            logger.warning(f"Failed to get memory for session {session_id}: {e}")
            return []
        finally:
            if memory:
                try:
                    client = memory.get_client()
                    await client.aclose()
                except Exception as e:
                    logger.warning(
                        f"Error closing Redis client for session {session_id}: {e}"
                    )

    async def delete_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> None:
        """Delete a session."""
        memory = None
        try:
            memory = RedisMemory(
                connection_pool=self.get_connection_pool(),
                user_id=user_id or session_id,
                session_id=session_id,
            )
            await memory.clear()
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")
        finally:
            if memory:
                try:
                    client = memory.get_client()
                    await client.aclose()
                except Exception as e:
                    logger.warning(
                        f"Error closing Redis client for session {session_id}: {e}"
                    )

    async def load_session_state(
        self, session_id: str, agent: AgentBase, user_id: Optional[str] = None
    ) -> None:
        """Load session state into agent.

        For Redis, session state is automatically managed by RedisMemory,
        so this is a no-op.
        """
        # Redis session state is automatically managed by RedisMemory
        # No manual loading needed
        pass

    async def save_session_state(
        self, session_id: str, agent: AgentBase, user_id: Optional[str] = None
    ) -> None:
        """Save agent state to session.

        For Redis, session state is automatically managed by RedisMemory,
        so this is a no-op.
        """
        # Redis session state is automatically managed by RedisMemory
        # No manual saving needed
        pass


class TTLJSONSessionHistoryService(JSONSessionHistoryService):
    """
    JSONSessionHistoryService with TTL-based automatic cleanup.
    Uses file modification time to determine session expiration.
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        cleanup_interval: int = 60,
        session_cleanup_callback: Optional[Callable[[str], Awaitable[None]]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._session_cleanup_callback = session_cleanup_callback
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._cleanup_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the cleanup task."""
        await super().start()
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        await super().stop()

    async def health(self) -> bool:
        """Check if the service is running."""
        return self._running

    async def _cleanup_loop(self) -> None:
        """Main cleanup loop that runs periodically."""
        try:
            while await self.health():
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_once()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_once(self) -> None:
        """Perform one cleanup cycle: scan files and delete expired sessions."""
        async with self._cleanup_lock:
            try:
                session_files = self._get_session_files()
                now = time.time()
                expired_sessions: List[str] = []

                for file_path in session_files:
                    try:
                        # Get file modification time
                        mtime = os.path.getmtime(file_path)
                        # Check if expired
                        if now - mtime > self._ttl_seconds:
                            session_id = self._get_session_id_from_path(file_path)
                            if session_id:
                                expired_sessions.append(session_id)
                    except (OSError, ValueError) as e:
                        logger.warning(
                            f"Failed to check file {file_path} for expiration: {e}"
                        )
                        continue

                # Delete expired sessions
                for session_id in expired_sessions:
                    try:
                        await self.delete_session(session_id)
                        logger.info(f"Deleted expired session: {session_id}")

                        # Call cleanup callback if provided
                        if self._session_cleanup_callback:
                            try:
                                await self._session_cleanup_callback(session_id)
                            except Exception as e:
                                logger.warning(
                                    f"Failed to cleanup session lock for {session_id}: {e}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete expired session {session_id}: {e}"
                        )

            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    def _get_session_files(self) -> List[str]:
        """Get all session JSON files from the save directory."""
        session_files = []
        save_dir = self.session.save_dir

        if not os.path.exists(save_dir):
            return session_files

        try:
            for filename in os.listdir(save_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(save_dir, filename)
                    if os.path.isfile(file_path):
                        session_files.append(file_path)
        except OSError as e:
            logger.warning(f"Failed to list session files in {save_dir}: {e}")

        return session_files

    def _get_session_id_from_path(self, file_path: str) -> Optional[str]:
        """Extract session ID from file path."""
        try:
            filename = os.path.basename(file_path)
            if filename.endswith(".json"):
                return filename[:-5]  # Remove .json extension
            return None
        except Exception as e:
            logger.warning(f"Failed to extract session ID from {file_path}: {e}")
            return None


class FeedbackData(BaseModel):
    message_id: str = Field(..., description="The ID of the message being rated")
    feedback_type: Literal["like", "dislike"] = Field(
        ..., description="Must be 'like' or 'dislike'"
    )
    comment: str = Field("", description="Optional user comment")


class FeedbackRequest(BaseModel):
    data: FeedbackData
    session_id: str
    user_id: Optional[str] = None
    id: Optional[str] = None


class JuicerAgentRequest(AgentRequest):
    """Extra model parameters (e.g., {"enable_thinking": True})"""

    model_params: Optional[Dict[str, Any]] = None


async def add_qa_tools(
    toolkit: Toolkit,
):
    try:
        # Check and initialize RAG data if needed
        from rag_utils.create_rag_file import (
            check_rag_initialized,
            initialize_rag,
            SCRIPT_DIR,
        )

        collection_name = "dj_faq"
        is_initialized = await check_rag_initialized(collection_name)

        if not is_initialized:
            logger.info("RAG data not found. Initializing RAG data...")
            # Check for custom FAQ file in the qaagent_tools directory
            custom_faq_file = SCRIPT_DIR / "faq.txt"

            if custom_faq_file.exists():
                logger.info(f"Using FAQ file: {custom_faq_file}")
                await initialize_rag(
                    faq_file_path=custom_faq_file,
                    collection_name=collection_name,
                )
            else:
                logger.warning(
                    f"FAQ file not found at {custom_faq_file}. "
                    "Please ensure faq.txt exists "
                    "in the rag_utils directory.",
                )
                logger.info("Attempting to use default FAQ file...")
                await initialize_rag(collection_name=collection_name)
            logger.info("RAG data initialization completed.")
        else:
            logger.info(
                "RAG data already initialized. Skipping initialization.",
            )

        knowledge = SimpleKnowledge(
            embedding_store=QdrantStore(
                # location=":memory:",
                location=None,
                client_kwargs={
                    "host": os.getenv(
                        "QDRANT_HOST", "127.0.0.1"
                    ),  # Qdrant server address
                    "port": int(os.getenv("QDRANT_PORT", "6333")),  # Qdrant server port
                },
                collection_name="dj_faq",
                dimensions=1024,  # The dimension of the embedding vectors
            ),
            embedding_model=DashScopeTextEmbedding(
                api_key=os.environ["DASHSCOPE_API_KEY"],
                model_name="text-embedding-v4",
            ),
        )
        toolkit.register_tool_function(
            knowledge.retrieve_knowledge,
            func_description=(  # Provide a clear description for the tool
                "Quickly retrieve answers to questions related to "
                "the Data-juicer FAQ. The `query` parameter is crucial "
                "for retrieval quality."
                "You may try multiple different queries to get the best "
                "results. Adjust the `limit` and `score_threshold` "
                "parameters to control the number and relevance of results."
            ),
            # group_name="qa_mode",
        )
    except Exception as e:
        print(traceback.format_exc())
        raise e from None

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error(
            "Missing GITHUB_TOKEN; GitHub MCP tools cannot be used. "
            "Please export GITHUB_TOKEN in your environment before "
            "proceeding.",
        )
    else:
        try:
            github_client = HttpStatelessClient(
                name="github",
                transport="streamable_http",
                url="https://api.githubcopilot.com/mcp/",
                headers={"Authorization": (f"Bearer {github_token}")},
            )

            await toolkit.register_mcp_client(
                github_client,
                enable_funcs=[
                    "search_repositories",
                    "search_code",
                    "get_file_contents",
                ],
                # group_name="qa_mode",
            )
            # toolkit.register_tool_function(execute_shell_command)
        except Exception as e:
            print(traceback.format_exc())
            raise e from None

    # Initialize and register DJ Operator Retriever tools
    dj_retriever = DJOperatorRetriever()
    toolkit.register_tool_function(dj_retriever.search_operators)
    toolkit.register_tool_function(dj_retriever.get_operator_details)
    toolkit.register_tool_function(verify_urls)
