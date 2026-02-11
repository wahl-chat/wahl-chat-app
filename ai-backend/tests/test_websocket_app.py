# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
from datetime import datetime
from typing import Dict, List
import pytest
import socketio
import uuid
import multiprocessing

from src.models.dtos import (
    ChatResponseCompleteDto,
    ChatSessionInitializedDto,
    ChatUserMessageDto,
    InitChatSessionDto,
    PartyResponseCompleteDto,
    PartyResponseChunkDto,
    ProConPerspectiveRequestDto,
    ProConPerspectiveDto,
    QuickRepliesAndTitleDto,
    RespondingPartiesDto,
    SourcesDto,
    RequestSummaryDto,
    StatusIndicator,
    SummaryDto,
)
from src.models.context import ContextParty
from src.models.chat import Message
from src.utils import load_env


load_env()

BASE_URL = "http://localhost:8080"
# BASE_URL = (
#     "https://wahl-chat-api-dev.redisland-8be84878.westeurope.azurecontainerapps.io"
# )


class TestHelpers:
    @staticmethod
    async def send_and_verify_chat_session_init(
        client: socketio.Client, create_session_dto: InitChatSessionDto
    ):
        chat_session_initialized_future: asyncio.Future = asyncio.Future()

        @client.on("chat_session_initialized")
        def handle_chat_session_initialized(data):
            chat_session_initialized_future.set_result(data)

        # Start the chat session
        client.emit("chat_session_init", create_session_dto.model_dump())

        # Wait for the chat session to be initialized or timeout after 5 seconds
        try:
            chat_session_initialized_data = await asyncio.wait_for(
                chat_session_initialized_future, timeout=10
            )
        except asyncio.TimeoutError:
            pytest.fail("Chat session not initialized within timeout.")

        assert chat_session_initialized_data
        chat_session_initialized_dto = ChatSessionInitializedDto(
            **chat_session_initialized_data
        )
        assert chat_session_initialized_dto.session_id == create_session_dto.session_id

    @staticmethod
    async def test_chat_session_helper(
        client: socketio.Client,
        create_session_dto: InitChatSessionDto,
        chat_user_messages: List[ChatUserMessageDto],
    ):
        # Start the chat session
        await TestHelpers.send_and_verify_chat_session_init(client, create_session_dto)

        sources_timeout = 60  # needed more that 10 seconds occasionally
        response_timeout = 40  # needed more that 20 seconds occasionally
        chat_title_and_quick_replies_timeout = (
            10  # needed more that 5 seconds occasionally
        )

        # Set up event handlers
        @client.on("responding_parties_selected")
        def handle_responding_parties_selected(data):
            responding_parties_selected_future.set_result(data)

        @client.on("sources_ready")
        def handle_sources(data):
            party_id = data["party_id"] if data.get("party_id") else "perplexity"
            # Check if the future is already done
            if not sources_ready_futures[party_id].done():
                sources_ready_futures[party_id].set_result(data)
            else:
                print(
                    f"Warning: Duplicate 'sources_ready' event received for {party_id}. Data: {data}"
                )

        @client.on("party_response_chunk_ready")
        def handle_response_chunk(data):
            party_id = data["party_id"] if data.get("party_id") else "perplexity"
            # check if the party_id is in the party_response_chunks dictionary
            if party_id not in party_response_chunks:
                party_response_chunks[party_id] = []
            # assert that chunk_index is the next index in the list and print the index, party_id and chunk_content if the assertion fails
            assert (
                data["chunk_index"] == len(party_response_chunks[party_id])
            ), f"Chunk index: {data['chunk_index']}, Party ID: {party_id}, Chunk content: {data['chunk_content']}, complete party response chunks dict: {party_response_chunks}"

            response_chunk = PartyResponseChunkDto(**data)

            party_response_chunks[party_id].append(response_chunk)

        @client.on("party_response_complete")
        def handle_party_response_complete(data):
            party_id = data["party_id"] if data.get("party_id") else "perplexity"
            print(f"Party response complete for {party_id}: {data}")
            # Check if the future is already done
            if not party_response_completed_futures[party_id].done():
                party_response_completed_futures[party_id].set_result(data)
            else:
                print(
                    f"Warning: Duplicate 'party_response_complete' event received for {party_id}. Data: {data}"
                )

        @client.on("quick_replies_and_title_ready")
        def handle_quick_replies_and_title(data):
            # Check if the future is already done
            if not chat_title_and_quick_replies_future.done():
                chat_title_and_quick_replies_future.set_result(data)
            else:
                print(
                    f"Warning: Duplicate 'quick_replies_and_title_ready' event received. Data: {data}"
                )

        for _, chat_user_message in enumerate(chat_user_messages):
            # Set up futures for the responses
            responding_parties_selected_future: asyncio.Future = asyncio.Future()
            sources_ready_futures: Dict[str, asyncio.Future] = {}
            party_response_completed_futures: Dict[str, asyncio.Future] = {}
            chat_title_and_quick_replies_future: asyncio.Future = asyncio.Future()
            party_response_chunks: Dict[str, list] = {}
            for party_id in chat_user_message.party_ids:
                sources_ready_futures[party_id] = asyncio.Future()
                party_response_completed_futures[party_id] = asyncio.Future()
                party_response_chunks[party_id] = []

            client.emit("chat_answer_request", chat_user_message.model_dump())

            # Wait for the responding parties
            try:
                responding_parties_selected_data = await asyncio.wait_for(
                    responding_parties_selected_future, timeout=5
                )
            except asyncio.TimeoutError:
                pytest.fail("Responding parties not selected within timeout.")
            assert responding_parties_selected_data
            responding_parties_dto = RespondingPartiesDto(
                **responding_parties_selected_data
            )
            assert responding_parties_dto.session_id == create_session_dto.session_id
            print(f"Received responding parties: {responding_parties_dto}")

            active_party_ids = responding_parties_dto.party_ids

            # Wait for the sources to be ready
            try:
                sources_data = await asyncio.gather(
                    *(
                        asyncio.wait_for(
                            sources_ready_futures[party_id], timeout=sources_timeout
                        )
                        for party_id in active_party_ids
                    )
                )
            except asyncio.TimeoutError:
                pytest.fail("Sources not ready within timeout.")

            assert sources_data
            assert len(sources_data) == len(responding_parties_dto.party_ids)
            for sources in sources_data:
                sources_dto = SourcesDto(**sources)
                assert sources_dto.session_id == create_session_dto.session_id
                print(f"Sources for {sources_dto.party_id}: {sources_dto}")

            # Wait for the response chunks
            try:
                response_completed_data = await asyncio.gather(
                    *(
                        asyncio.wait_for(
                            party_response_completed_futures[party_id],
                            timeout=response_timeout,
                        )
                        for party_id in active_party_ids
                    )
                )
            except asyncio.TimeoutError:
                pytest.fail("Response chunks not received within timeout.")
            assert response_completed_data
            assert len(response_completed_data) == len(responding_parties_dto.party_ids)

            for party_response_completed in response_completed_data:
                party_response_complete_dto = PartyResponseCompleteDto(
                    **party_response_completed
                )
                print(f"Response dto: {party_response_complete_dto}")
                assert (
                    party_response_complete_dto.session_id
                    == create_session_dto.session_id
                )
                assert party_response_complete_dto.status.indicator == "success"
            # Wait for the chat title and quick replies
            try:
                chat_title_and_quick_replies_data = await asyncio.wait_for(
                    chat_title_and_quick_replies_future,
                    timeout=chat_title_and_quick_replies_timeout,
                )
            except asyncio.TimeoutError:
                pytest.fail("Chat title and quick replies not received within timeout.")
            assert chat_title_and_quick_replies_data
            chat_title_and_quick_replies_dto = QuickRepliesAndTitleDto(
                **chat_title_and_quick_replies_future.result()
            )
            print(f"Chat title and quick replies: {chat_title_and_quick_replies_dto}")
            assert (
                chat_title_and_quick_replies_dto.session_id
                == create_session_dto.session_id
            )


@pytest.fixture(scope="module")
def client():
    """Create a socket.io client for testing."""
    client = socketio.Client()
    client.connect(BASE_URL, transports=["websocket"])
    return client
    # yield client
    # client.disconnect()


@pytest.fixture(scope="module")
def test_helpers():
    return TestHelpers


@pytest.mark.asyncio
async def test_home_response(client: socketio.Client):
    """Test the `home` endpoint."""
    home_response_future: asyncio.Future = (
        asyncio.Future()
    )  # Future to hold the server response

    @client.on("home_response")
    def handle_response(data):
        home_response_future.set_result(data)

    client.emit("home", {})

    # Wait for the server response or timeout after 5 seconds
    try:
        response = await asyncio.wait_for(home_response_future, timeout=5)
        assert response
    except asyncio.TimeoutError:
        pytest.fail("Home response not received within timeout.")


@pytest.mark.asyncio
async def test_get_chat_answer(client: socketio.Client, test_helpers: TestHelpers):
    """Test the get_chat_answer endpoint."""
    mock_parties = [
        ContextParty(
            party_id="spd",
            name="SPD",
            long_name="Sozialdemokratische Partei Deutschlands",
            description="Die SPD ist eine sozialdemokratische Partei in Deutschland.",
            website_url="https://www.spd.de/",
            candidate="Olaf Scholz",
            manifesto_url="https://www.spd.de/manifesto",
        ),
        ContextParty(
            party_id="gruene",
            name="Bündnis 90/Die Grünen",
            long_name="Bündnis 90/Die Grünen",
            description="Die Grünen sind eine politische Partei in Deutschland.",
            website_url="https://www.gruene.de",
            candidate="Annalena Baerbock",
            manifesto_url="https://www.gruene.de/manifesto",
        ),
    ]

    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Wie stehen die SPD und die Grüne zum Klimaschutz?",
            party_ids=[party.party_id for party in mock_parties],
        ),
    ]

    await test_helpers.test_chat_session_helper(
        client, create_session_dto, chat_user_messages
    )


@pytest.mark.asyncio
async def test_get_specific_party_answer(
    client: socketio.Client, test_helpers: TestHelpers
):
    """Test whether the correct party is selected for the response."""
    mock_parties = [
        ContextParty(
            party_id="spd",
            name="SPD",
            long_name="Sozialdemokratische Partei Deutschlands",
            description="Die SPD ist eine sozialdemokratische Partei in Deutschland.",
            website_url="https://www.spd.de/",
            candidate="Olaf Scholz",
            manifesto_url="https://www.spd.de/manifesto",
        ),
        ContextParty(
            party_id="gruene",
            name="Bündnis 90/Die Grünen",
            long_name="Bündnis 90/Die Grünen",
            description="Die Grünen sind eine politische Partei in Deutschland.",
            website_url="https://www.gruene.de",
            candidate="Annalena Baerbock",
            manifesto_url="https://www.gruene.de/manifesto",
        ),
    ]

    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Wie steht die SPD zum Klimaschutz?",
            party_ids=[party.party_id for party in mock_parties],
        ),
    ]

    await test_helpers.test_chat_session_helper(
        client, create_session_dto, chat_user_messages
    )


@pytest.mark.asyncio
async def test_get_pro_con_perspective(client: socketio.Client):
    """Test the `pro_con_perspective` events."""
    payload = {
        "request_id": str(uuid.uuid4()),
        "party_id": "gruene",
        "last_user_message": "Was sind die Nachteile erneuerbarer Energien?",
        "last_assistant_message": "Erneuerbare Energien sind nachhaltig und umweltfreundlich.",
    }

    payload_dto = ProConPerspectiveRequestDto(**payload)

    response_future: asyncio.Future = (
        asyncio.Future()
    )  # Future to hold the server response

    @client.on("pro_con_perspective_complete")
    def handle_pro_con_response(data):
        response_future.set_result(data)

    client.emit("pro_con_perspective_request", payload_dto.model_dump())

    # Wait for the server response or timeout after 20 seconds
    try:
        response = await asyncio.wait_for(response_future, timeout=20)
    except asyncio.TimeoutError:
        pytest.fail("Pro/Con perspective not received within timeout.")

    assert response
    pro_con_response_dto = ProConPerspectiveDto(**response)
    assert pro_con_response_dto.request_id == payload_dto.request_id
    assert pro_con_response_dto.message is not None
    assert len(pro_con_response_dto.message.content) > 0


@pytest.mark.asyncio
async def test_chat_session_init(client: socketio.Client, test_helpers: TestHelpers):
    """Test the `chat_session_init` event."""
    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    await test_helpers.send_and_verify_chat_session_init(client, create_session_dto)


@pytest.mark.asyncio
async def test_get_chat_summary(client: socketio.Client):
    """Test the `get_chat_summary` event."""
    # mock a chat history with messages
    chat_history = [
        Message(role="user", content="Wie steht die SPD zum Klimaschutz?", sources=[]),
        Message(
            role="assistant",
            content="Die SPD setzt sich für den Klimaschutz ein.",
            sources=[],
        ),
        Message(
            role="user",
            content="Was sind die Vorteile von erneuerbaren Energien?",
            sources=[],
        ),
        Message(
            role="assistant",
            content="Erneuerbare Energien sind nachhaltig und umweltfreundlich.",
            sources=[],
        ),
    ]

    request_summary_dto = RequestSummaryDto(chat_history=chat_history)

    chat_summary_complete_future: asyncio.Future = asyncio.Future()

    # client for a received summary
    @client.on("chat_summary_complete")
    def handle_chat_summary_complete(data):
        chat_summary_complete_future.set_result(data)

    # get the chat summary
    client.emit("chat_summary_request", request_summary_dto.model_dump())

    # Wait for the chat summary to be complete or timeout after 20 seconds
    try:
        chat_summary_complete_data = await asyncio.wait_for(
            chat_summary_complete_future, timeout=20
        )
    except asyncio.TimeoutError:
        pytest.fail("Chat summary not received within timeout.")

    assert chat_summary_complete_data
    # validate the chat summary data
    _ = SummaryDto(**chat_summary_complete_data)


# tests with multiple messages in a row
@pytest.mark.asyncio
async def test_get_multiple_chat_answers(
    client: socketio.Client, test_helpers: TestHelpers
):
    """Test getting multiple chat answers in a row."""
    mock_parties = [
        ContextParty(
            party_id="spd",
            name="SPD",
            long_name="Sozialdemokratische Partei Deutschlands",
            description="Die SPD ist eine sozialdemokratische Partei in Deutschland.",
            website_url="https://www.spd.de/",
            candidate="Olaf Scholz",
            manifesto_url="https://www.spd.de/manifesto",
        ),
        ContextParty(
            party_id="gruene",
            name="Bündnis 90/Die Grünen",
            long_name="Bündnis 90/Die Grünen",
            description="Die Grünen sind eine politische Partei in Deutschland.",
            website_url="https://www.gruene.de",
            candidate="Annalena Baerbock",
            manifesto_url="https://www.gruene.de/manifesto",
        ),
    ]

    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Wie stehen die SPD und die Grüne zum Klimaschutz?",
            party_ids=[party.party_id for party in mock_parties],
        ),
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Was sind die Nachteile erneuerbarer Energien?",
            party_ids=[party.party_id for party in mock_parties],
        ),
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Was ist rot und fällt vom Baum? Ein rotes Klavier.",
            party_ids=[party.party_id for party in mock_parties],
        ),
    ]

    await test_helpers.test_chat_session_helper(
        client, create_session_dto, chat_user_messages
    )


# uncomment user messages to send invalid requests and check for error responses
@pytest.mark.asyncio
async def test_send_invalid_user_message_objects(
    client: socketio.Client, test_helpers: TestHelpers
):
    mock_parties = [
        ContextParty(
            party_id="spd",
            name="SPD",
            long_name="Sozialdemokratische Partei Deutschlands",
            description="Die SPD ist eine sozialdemokratische Partei in Deutschland.",
            website_url="https://www.spd.de/",
            candidate="Olaf Scholz",
            manifesto_url="https://www.spd.de/manifesto",
        ),
        ContextParty(
            party_id="gruene",
            name="Bündnis 90/Die Grünen",
            long_name="Bündnis 90/Die Grünen",
            description="Die Grünen sind eine politische Partei in Deutschland.",
            website_url="https://www.gruene.de",
            candidate="Annalena Baerbock",
            manifesto_url="https://www.gruene.de/manifesto",
        ),
    ]

    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        # {
        #     "session_id": "",  # empty session id
        #     "user_message": "Wie stehen die SPD und die Grüne zum Klimaschutz?",
        #     "party_ids": [party.party_id for party in mock_parties],
        # },
        # {
        #     "session_id": chat_session_id,
        #     "user_message": 1,  # non string user message
        #     "party_ids": [party.party_id for party in mock_parties],
        # },
        # {
        #     "session_id": chat_session_id,
        #     "user_message": "Was sind die Nachteile erneuerbarer Energien?",  # non ChatUserMessageDto object
        #     "party_ids": [party.party_id for party in mock_parties],
        # },
        # {
        #     "wrong_key": chat_session_id,  # wrong key
        #     # missing user_message key
        # },
        {
            "session_id": chat_session_id,
            # a user message that is longer than 500 characters (specifically 501 characters)
            "user_message": "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea",
            "party_ids": [party.party_id for party in mock_parties],
        },
    ]

    await test_helpers.send_and_verify_chat_session_init(client, create_session_dto)

    for chat_user_message in chat_user_messages:
        chat_response_complete_future: asyncio.Future = asyncio.Future()

        @client.on("chat_response_complete")
        def handle_response(data):
            chat_response_complete_future.set_result(data)

        client.emit("chat_answer_request", chat_user_message)

        try:
            response = await asyncio.wait_for(chat_response_complete_future, timeout=10)
        except asyncio.TimeoutError:
            pytest.fail("Response not received within timeout.")

        assert response
        response_dto = ChatResponseCompleteDto(**response)
        assert response_dto.status.indicator == StatusIndicator.ERROR.value


@pytest.mark.asyncio
async def test_get_comparing_chat_answer(
    client: socketio.Client, test_helpers: TestHelpers
):
    """Test the get_chat_answer endpoint."""
    mock_parties = [
        ContextParty(
            party_id="spd",
            name="SPD",
            long_name="Sozialdemokratische Partei Deutschlands",
            description="Die SPD ist eine sozialdemokratische Partei in Deutschland.",
            website_url="https://www.spd.de/",
            candidate="Olaf Scholz",
            manifesto_url="https://www.spd.de/manifesto",
        ),
        ContextParty(
            party_id="gruene",
            name="Bündnis 90/Die Grünen",
            long_name="Bündnis 90/Die Grünen",
            description="Die Grünen sind eine politische Partei in Deutschland.",
            website_url="https://www.gruene.de",
            candidate="Annalena Baerbock",
            manifesto_url="https://www.gruene.de/manifesto",
        ),
    ]

    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Wie unterscheidet sich der Klimaschutz bei der SPD und den Grünen?",
            party_ids=[party.party_id for party in mock_parties],
        ),
    ]

    await test_helpers.test_chat_session_helper(
        client, create_session_dto, chat_user_messages
    )


# test that tests the cpu and memory usage and the response time with multiple parallel requests
@pytest.mark.asyncio
async def test_mock_parallel_requests():
    client = socketio.Client()
    client.connect(BASE_URL, transports=["websocket"])

    result_list = []
    response_complete = asyncio.Future()

    chat_session_id = str(uuid.uuid4())

    @client.on("mock_response_chunk_ready")
    def handle_mock_response_chunk_ready(data):
        result_list.append(data["message"])

    @client.on("mock_response_complete")
    def handle_mock_response_complete(data):
        session_end_time = datetime.now()
        print(f"Session {chat_session_id} end time: {session_end_time}")
        print(
            f"Session {chat_session_id} duration: {session_end_time - session_start_time}"
        )
        response_complete.set_result(data)

    # create a chat session
    session_start_time = datetime.now()
    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    client.emit("mock_websocket_usage", create_session_dto.model_dump())

    try:
        _ = await asyncio.wait_for(response_complete, timeout=120)
    except asyncio.TimeoutError:
        pytest.fail("Response not received within timeout.")

    assert response_complete

    client.disconnect()


def run_test_in_process():
    """Run the test in a separate process."""
    asyncio.run(test_mock_parallel_requests())


def test_run_benchmark():
    num_processes = 1  # max tested with 128
    processes = []

    for _ in range(num_processes):
        p = multiprocessing.Process(target=run_test_in_process, args=())
        processes.append(p)
        p.start()

    for p in processes:
        p.join()


# testing one of the cached questions
@pytest.mark.asyncio
def test_cached_questions(client: socketio.Client, test_helpers: TestHelpers):
    chat_session_id = str(uuid.uuid4())

    create_session_dto = InitChatSessionDto(
        session_id=chat_session_id,
        chat_history=[],
        current_title="Test Chat",
        created_at=datetime.now(),
    )

    chat_user_messages = [
        ChatUserMessageDto(
            session_id=chat_session_id,
            user_message="Was sind die wichtigsten Ziele der Parteien?",
            party_ids=["cdu"],
        ),
    ]

    asyncio.run(
        test_helpers.test_chat_session_helper(
            client, create_session_dto, chat_user_messages
        )
    )
