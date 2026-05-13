"""Create one session each in groups A1 / B1 / C1 (one per condition family, topic1)."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.models.session import get_condition_for_group  # noqa: E402
from src.exploration_study.services.session_repository import get_session_repository  # noqa: E402
from src.exploration_study.services.study_repository import get_study_repository  # noqa: E402


async def main(study_id: str, out_path: str) -> int:
    study_repo = get_study_repository()
    session_repo = get_session_repository()
    study = await study_repo.get_study(study_id)
    if not study:
        print(f"Study not found: {study_id}", file=sys.stderr)
        return 1

    groups = ["A1", "B1", "C1"]
    session_ids: list[str] = []
    for group in groups:
        condition = get_condition_for_group(group, study.config.topics)
        session = await session_repo.create_session(
            study_id=study_id,
            group=group,
            condition=condition,
        )
        session_ids.append(session.id)
        print(f"  {group}: {session.id}  ({condition.system.value} / {condition.topic})")

    with open(out_path, "w") as f:
        for sid in session_ids:
            f.write(f"{sid}\n")
    print(f"\nWrote {len(session_ids)} session ids to {out_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: _create_one_per_family.py <study_id> <out_path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
