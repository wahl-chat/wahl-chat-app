# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import argparse
import logging
import os
import json

from aiohttp import web
import aiohttp_cors
from aiohttp_pydantic.decorator import inject_params

from src.chatbot_async import (
    generate_swiper_assistant_response,
    generate_swiper_assistant_title_and_chick_replies,
    get_improved_rag_query_voting_behavior,
)
from src.firebase_service import aget_party_by_id
from src.models.chat import Message, Role
from src.models.dtos import (
    ParliamentaryQuestionDto,
    ParliamentaryQuestionRequestDto,
    Status,
    StatusIndicator,
    WahlChatSwiperAnswerDto,
    WahlChatSwiperAnswerRequestDto,
)
from src.models.vote import Vote
from src.vector_store_helper import identify_relevant_parliamentary_questions
from src.utils import build_chat_history_string, get_cors_allowed_origins
from src.websocket_app import sio

LOGGING_FORMAT = (
    "%(asctime)s - %(name)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
)
# Set up default logging configuration
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)

logger = logging.getLogger(__name__)

app = web.Application()

routes = web.RouteTableDef()

route_prefix = "/api/v1"


@web.middleware
async def api_key_middleware(request, handler):
    if request.method == "OPTIONS":
        return await handler(request)

    # TODO: implement authentication here, if needed
    return await handler(request)


@routes.get("/healthz")
async def health_check(request):
    """Kubernetes health check endpoint."""
    return web.json_response({"status": "ok"})


@routes.post(f"{route_prefix}/get-parliamentary-question")
@inject_params
async def get_parliamentary_question(body: ParliamentaryQuestionRequestDto):
    party = await aget_party_by_id(body.party_id)

    if not party:
        return web.json_response(
            ParliamentaryQuestionDto(
                request_id=body.request_id,
                status=Status(
                    indicator=StatusIndicator.ERROR,
                    message="Could not find party with the provided ID",
                ),
                parliamentary_questions=[],
                rag_query=None,
            ).model_dump()
        )

    improved_rag_query = await get_improved_rag_query_voting_behavior(
        party, body.last_user_message, body.last_assistant_message
    )
    logger.debug(f"Improved RAG query: {improved_rag_query}")
    relevant_parliamentary_questions = await identify_relevant_parliamentary_questions(
        body.party_id, improved_rag_query
    )

    logger.debug(
        f"Relevant parliamentary questions: {relevant_parliamentary_questions}"
    )

    parliamentary_questions: list[Vote] = []
    for vote_doc in relevant_parliamentary_questions:
        vote_data_json_str = vote_doc.metadata.get("vote_data_json_str", "{}")
        vote_data = json.loads(vote_data_json_str)
        parliamentary_question = Vote(**vote_data)
        parliamentary_questions.append(parliamentary_question)

    parliamentary_question_dto = ParliamentaryQuestionDto(
        request_id=body.request_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        parliamentary_questions=parliamentary_questions,
        rag_query=improved_rag_query,
    )

    return web.json_response(parliamentary_question_dto.model_dump())


@routes.post(f"{route_prefix}/answer-wahl-chat-swiper-question")
@inject_params
async def answer_wahl_chat_swiper_question(body: WahlChatSwiperAnswerRequestDto):
    logger.debug(f"Received request: {body}")

    user_message = Message(
        role=Role.USER,
        content=body.user_message,
    )

    chat_history_str = build_chat_history_string(
        body.chat_history, [], default_assistant_name="wahl.chat Swiper Assistent"
    )

    swiper_assistant_response = await generate_swiper_assistant_response(
        current_political_question=body.current_political_question,
        conversation_history=chat_history_str,
        user_message=body.user_message,
        chat_response_llm_size=body.chat_response_llm_size,
    )

    chat_history = body.chat_history
    chat_history.append(user_message)
    chat_history.append(swiper_assistant_response)

    chat_history_str = build_chat_history_string(
        chat_history, [], default_assistant_name="wahl.chat Swiper Assistent"
    )

    title_and_quick_replies = await generate_swiper_assistant_title_and_chick_replies(
        chat_history_str, body.current_political_question
    )

    wahl_chat_swiper_answer_dto = WahlChatSwiperAnswerDto(
        message=swiper_assistant_response,
        title=title_and_quick_replies.chat_title,
        quick_replies=title_and_quick_replies.quick_replies,
    )

    return web.json_response(wahl_chat_swiper_answer_dto.model_dump())


app = web.Application(middlewares=[api_key_middleware])

# Add routes to the app
app.router.add_routes(routes)

# Configure CORS
# Configure default CORS settings.
default_resource_options = aiohttp_cors.ResourceOptions(
    allow_credentials=True,
    expose_headers="*",
    allow_headers="*",
    allow_methods="*",
)
cors_allowed_origins = get_cors_allowed_origins(os.getenv("ENV"))
cors_config = {}
if type(cors_allowed_origins) is str:
    cors_config[cors_allowed_origins] = default_resource_options
else:
    for origin in cors_allowed_origins:
        cors_config[origin] = default_resource_options


logger.info(f"CORS allowed origins: {cors_config}")

cors = aiohttp_cors.setup(
    app,
    # defaults=cors_config,
)


# Configure CORS on all routes
for route in list(app.router.routes()):
    logger.info(f"Adding CORS to route {route}")
    cors.add(route, cors_config)

sio.attach(app)


# Instantiate the argument parser
parser = argparse.ArgumentParser()

# Add arguments to parser
parser.add_argument("--host", type=str, nargs=1, default=["127.0.0.1"])
parser.add_argument("--port", type=int, nargs=1, default=[8080])
parser.add_argument("--debug", action="store_true", default=False)

# Start the server
if __name__ == "__main__":
    args = parser.parse_args()
    host = args.host[0]
    port = args.port[0]
    debug = args.debug
    socketio_logger = logging.getLogger("socketio.asyncserver")
    if debug:
        socketio_logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        # Set all loggers in the src package to debug
        for logger in loggers:
            if logger.name.startswith("src"):
                logger.setLevel(logging.DEBUG)
    else:
        socketio_logger.setLevel(logging.WARN)
        logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
    web.run_app(app, host=host, port=port)
