# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import datetime
import json
from src.models.vote import Vote


def convert_party_short_hand_to_party_id(party_short_hand: str) -> str:
    mapping = {
        "CDU/CSU": "cdu",
        "CDU": "cdu",
        "SPD": "spd",
        "DIE LINKE.": "linke",
        "LINKE": "linke",
        "B90/GRÜNE": "gruene",
        "GRÜNE": "gruene",
        "FDP": "fdp",
        "AfD": "afd",
        "AFD": "afd",
        "Volt": "volt",
        "BSW": "bsw",
        "fraktionslose": "fraktionslose",
        "FRAKTIONSLOS": "fraktionslose",
        "fraktionslos": "fraktionslose",
    }
    return mapping.get(party_short_hand, party_short_hand)


def ensure_uniform_vote_object_data(vote_obj: Vote):
    # Convert the party short hand to party id
    if vote_obj.submitting_parties is not None:
        vote_obj.submitting_parties = [
            convert_party_short_hand_to_party_id(party)
            for party in vote_obj.submitting_parties
        ]

    # Convert the date from (e.g. 9. März 2017 -> 2017-03-09)
    date_obj = datetime.strptime(vote_obj.date, "%d. %B %Y")
    vote_obj.date = date_obj.strftime("%Y-%m-%d")


def create_vote_metadata_for_pinecone(vote: Vote):
    return {
        "vote_id": vote.id,
        "title": vote.title,
        "subtitle": vote.subtitle,
        "date": vote.date,
        "vote_category": vote.vote_category,
        "text_source": "short_description",
        "url": vote.url,
        "vote_data_json_str": json.dumps(vote.model_dump(), ensure_ascii=False),
    }


def load_vote(vote_id: int) -> Vote:
    with open(f"../votes/vote_{vote_id}.json", "r") as f:
        return Vote.model_validate_json(f.read())
