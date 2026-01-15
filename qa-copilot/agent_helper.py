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
import asyncio
import time
import traceback
from loguru import logger
from typing import Optional, Dict, Any, List, Union, Literal
from pydantic import BaseModel, Field

from agentscope.mcp import HttpStatelessClient
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.rag import SimpleKnowledge, QdrantStore
from agentscope.tool import execute_shell_command, Toolkit

from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.schemas.session import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message

from op_manager.dj_op_retriever import DJOperatorRetriever


class TTLInMemorySessionHistoryService(InMemorySessionHistoryService):
    def __init__(
        self, ttl_seconds: int = 3600, cleanup_interval: int = 60, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval

        self._last_access: Dict[str, Dict[str, float]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._ttl_lock = asyncio.Lock()

    def _touch(self, user_id: str, session_id: str) -> None:
        self._last_access.setdefault(user_id, {})[session_id] = time.time()

    async def start(self) -> None:
        await super().start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        async with self._ttl_lock:
            self._last_access.clear()

        await super().stop()

    async def _cleanup_loop(self) -> None:
        try:
            while await self.health():
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_once()
        except asyncio.CancelledError:
            return

    async def _cleanup_once(self) -> None:
        now = time.time()
        expired: List[tuple[str, str]] = []

        async with self._ttl_lock:
            for user_id, m in list(self._last_access.items()):
                for session_id, ts in list(m.items()):
                    if now - ts > self._ttl_seconds:
                        expired.append((user_id, session_id))
                        del m[session_id]
                if not m:
                    del self._last_access[user_id]

        for user_id, session_id in expired:
            try:
                await super().delete_session(user_id, session_id)
            except Exception as e:
                print(
                    f"Failed to delete expired session {session_id} for user {user_id}: {e}"
                )

    async def create_session(
        self, user_id: str, session_id: Optional[str] = None
    ) -> Session:
        s = await super().create_session(user_id, session_id=session_id)
        async with self._ttl_lock:
            self._touch(user_id, s.id)
        return s

    async def get_session(self, user_id: str, session_id: str) -> Optional[Session]:
        s = await super().get_session(user_id, session_id)
        if s is not None:
            async with self._ttl_lock:
                self._touch(user_id, session_id)
        return s

    async def append_message(
        self,
        session: Session,
        message: Union[Message, List[Message], Dict[str, Any], List[Dict[str, Any]]],
    ) -> None:
        await super().append_message(session, message)
        async with self._ttl_lock:
            self._touch(session.user_id, session.id)

    async def delete_session(self, user_id: str, session_id: str) -> None:
        async with self._ttl_lock:
            if user_id in self._last_access:
                self._last_access[user_id].pop(session_id, None)
                if not self._last_access[user_id]:
                    self._last_access.pop(user_id, None)
        await super().delete_session(user_id, session_id)


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
                    "host": os.getenv("QDRANT_HOST", "127.0.0.1"),  # Qdrant server address
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
