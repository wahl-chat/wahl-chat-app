# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firebase repository for guided exploration sessions."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from firebase_admin import firestore_async
from google.cloud.firestore_v1 import DocumentReference, async_transactional

from src.guided_exploration.models import (
    Conversation,
    Exploration,
    ExplorationStatus,
    ExplorationTree,
    FlaggedCitation,
    Message,
    NodeStatus,
    Session,
    SessionMessage,
    SessionMode,
)

logger = logging.getLogger(__name__)

# Collection names
SESSIONS_COLLECTION = "guided_exploration_sessions"
EXPLORATIONS_SUBCOLLECTION = "explorations"
CONVERSATIONS_SUBCOLLECTION = "conversations"


class SessionRepository:
    """Firebase repository for guided exploration session persistence."""

    def __init__(self) -> None:
        self._db = firestore_async.client()

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        context_id: str,
        user_id: str | None = None,
        mode: SessionMode = SessionMode.GUIDED,
        max_claims_per_party: int | None = None,
    ) -> Session:
        """Create a new session."""
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        session = Session(
            id=session_id,
            context_id=context_id,
            user_id=user_id,
            mode=mode,
            max_claims_per_party=max_claims_per_party,
            created_at=now,
            last_active_at=now,
            preferences={},
        )

        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.set(session.model_dump(mode="json"))

        logger.info(f"Created session: {session_id} with mode={mode.value}")
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        return Session(**doc.to_dict())

    async def update_session_activity(self, session_id: str) -> None:
        """Update the last_active_at timestamp."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.update({"last_active_at": datetime.now(timezone.utc).isoformat()})

    async def update_session_active_exploration(
        self,
        session_id: str,
        exploration_id: str | None,
    ) -> None:
        """Update the active exploration for a session."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.update({"active_exploration_id": exploration_id})

    async def add_flagged_citation(
        self,
        session_id: str,
        flagged: FlaggedCitation,
    ) -> None:
        """Append a fabricated-citation record to the session.

        Auxiliary observability — the response itself still ships and the
        offending ids never enter exposure logging (they fail the pool
        intersection in ``extract_used_citations``). Failures here must
        not break the user-facing response.
        """
        from google.cloud.firestore_v1 import ArrayUnion

        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        try:
            await doc_ref.update(
                {"flagged_citations": ArrayUnion([flagged.model_dump(mode="json")])}
            )
        except Exception as e:
            logger.warning(
                f"add_flagged_citation failed for session={session_id}: "
                f"{type(e).__name__}: {e}"
            )

    # =========================================================================
    # Session Messages
    # =========================================================================

    async def add_session_message(
        self,
        session_id: str,
        message: SessionMessage,
    ) -> None:
        """Add a message to session-level chat."""
        from google.cloud.firestore_v1 import ArrayUnion

        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.update(
            {"messages": ArrayUnion([message.model_dump(mode="json")])}
        )

    async def update_session_message(
        self,
        session_id: str,
        message_id: str,
        updates: dict,
    ) -> None:
        """Update fields on a specific session message by ID.

        Wrapped in a Firestore transaction so concurrent updates on the
        ``messages`` array don't clobber each other — the array is read
        and written as a unit, and read-modify-write outside a transaction
        would race.
        """
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)

        @async_transactional
        async def _apply(tx) -> None:
            snapshot = await doc_ref.get(transaction=tx)
            if not snapshot.exists:
                return
            data = snapshot.to_dict() or {}
            raw_messages = data.get("messages", [])
            updated: list[dict] = []
            for raw in raw_messages:
                if raw.get("id") == message_id:
                    raw = {**raw, **updates}
                updated.append(raw)
            tx.update(doc_ref, {"messages": updated})

        await _apply(self._db.transaction())

    async def get_session_messages(
        self,
        session_id: str,
    ) -> list[SessionMessage]:
        """Get all session messages."""
        session = await self.get_session(session_id)
        return session.messages if session else []

    # =========================================================================
    # Exploration Operations
    # =========================================================================

    def _get_exploration_ref(
        self, session_id: str, exploration_id: str
    ) -> DocumentReference:
        """Get reference to an exploration document."""
        return (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection(EXPLORATIONS_SUBCOLLECTION)
            .document(exploration_id)
        )

    async def create_exploration(
        self,
        session_id: str,
        original_query: str,
        tree: ExplorationTree,
        exploration_id: str | None = None,
    ) -> Exploration:
        """
        Create a new exploration.

        Args:
            session_id: The session ID
            original_query: The user's original query
            tree: The topic tree structure
            exploration_id: Optional pre-generated exploration ID
        """
        exploration_id = exploration_id or str(uuid4())
        now = datetime.now(timezone.utc)

        exploration = Exploration(
            id=exploration_id,
            session_id=session_id,
            original_query=original_query,
            tree=tree,
            status=ExplorationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        doc_ref = self._get_exploration_ref(session_id, exploration_id)
        await doc_ref.set(exploration.model_dump(mode="json"))

        # Update session's active exploration
        await self.update_session_active_exploration(session_id, exploration_id)

        logger.info(f"Created exploration: {exploration_id} for session: {session_id}")
        return exploration

    async def get_exploration(
        self,
        session_id: str,
        exploration_id: str,
    ) -> Exploration | None:
        """Get an exploration by ID."""
        doc_ref = self._get_exploration_ref(session_id, exploration_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Exploration(**data)

    async def update_exploration(
        self,
        session_id: str,
        exploration_id: str,
        updates: dict,
    ) -> None:
        """Update exploration fields."""
        doc_ref = self._get_exploration_ref(session_id, exploration_id)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await doc_ref.update(updates)

    async def update_tree(
        self,
        session_id: str,
        exploration_id: str,
        tree: ExplorationTree,
    ) -> None:
        """Update the exploration's tree."""
        await self.update_exploration(
            session_id,
            exploration_id,
            {"tree": tree.model_dump(mode="json")},
        )

    async def complete_exploration(
        self,
        session_id: str,
        exploration_id: str,
    ) -> None:
        """Mark exploration as completed."""
        await self.update_exploration(
            session_id,
            exploration_id,
            {"status": ExplorationStatus.COMPLETED.value},
        )
        await self.update_session_active_exploration(session_id, None)

    async def get_active_exploration(
        self,
        session_id: str,
    ) -> Exploration | None:
        """Get the active exploration for a session."""
        session = await self.get_session(session_id)
        if not session or not session.active_exploration_id:
            return None

        return await self.get_exploration(session_id, session.active_exploration_id)

    async def list_explorations(
        self,
        session_id: str,
    ) -> list[dict]:
        """List all explorations for a session."""
        collection_ref = (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection(EXPLORATIONS_SUBCOLLECTION)
        )

        explorations: list[dict] = []
        async for doc in collection_ref.stream():
            data = doc.to_dict()
            if data:
                # Count explored vs total leaf nodes using the current schema.
                # The tree has a recursive root/children structure; walk it via
                # ExplorationTree so we don't hard-code the nesting depth.
                tree_data = data.get("tree", {})
                total_topics = 0
                explored_topics = 0
                try:
                    etree = ExplorationTree.model_validate(tree_data)
                    leaves = etree.root.get_leaf_nodes()
                    total_topics = len(leaves)
                    explored_topics = sum(
                        1 for leaf in leaves if leaf.status == NodeStatus.EXPLORED
                    )
                except Exception:
                    pass  # malformed tree — leave counts at 0

                explorations.append(
                    {
                        "id": data["id"],
                        "original_query": data.get("original_query", ""),
                        "status": data.get("status", "active"),
                        "created_at": data.get("created_at", ""),
                        "topics_explored": explored_topics,
                        "total_topics": total_topics,
                    }
                )
        return explorations

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def _get_conversation_ref(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> DocumentReference:
        """Get reference to a conversation document."""
        return (
            self._get_exploration_ref(session_id, exploration_id)
            .collection(CONVERSATIONS_SUBCOLLECTION)
            .document(leaf_id)
        )

    async def get_conversation(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> Conversation | None:
        """Get a conversation for a leaf node."""
        doc_ref = self._get_conversation_ref(session_id, exploration_id, leaf_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Conversation(**data)

    async def save_conversation(
        self,
        session_id: str,
        exploration_id: str,
        conversation: Conversation,
    ) -> None:
        """Save a conversation."""
        doc_ref = self._get_conversation_ref(
            session_id, exploration_id, conversation.leaf_id
        )
        await doc_ref.set(conversation.model_dump(mode="json"))

    async def add_message_to_conversation(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
        message: Message,
    ) -> None:
        """Add a message to an existing conversation."""
        doc_ref = self._get_conversation_ref(session_id, exploration_id, leaf_id)
        doc = await doc_ref.get()

        if doc.exists:
            # Append to existing messages
            from google.cloud.firestore_v1 import ArrayUnion

            await doc_ref.update(
                {"messages": ArrayUnion([message.model_dump(mode="json")])}
            )
        else:
            # Create new conversation with this message
            conversation = Conversation(
                leaf_id=leaf_id,
                messages=[message],
            )
            await doc_ref.set(conversation.model_dump(mode="json"))

    async def list_conversations(
        self,
        session_id: str,
        exploration_id: str,
    ) -> list[Conversation]:
        """List all conversations for an exploration."""
        collection_ref = self._get_exploration_ref(
            session_id, exploration_id
        ).collection(CONVERSATIONS_SUBCOLLECTION)

        conversations: list[Conversation] = []
        async for doc in collection_ref.stream():
            data = doc.to_dict()
            if data:
                conversations.append(Conversation(**data))

        return conversations


# Singleton instance
_repository: SessionRepository | None = None


def get_session_repository() -> SessionRepository:
    """Get or create the global session repository."""
    global _repository
    if _repository is None:
        _repository = SessionRepository()
    return _repository
