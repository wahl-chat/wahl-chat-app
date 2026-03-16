#!/usr/bin/env python3
"""
CLI tool for exploration study administration.

Usage:
    # Create a new study
    python scripts/exploration_study_admin.py create-study \
        --name "Pilot Study Feb 2026" \
        --context-id "study-fake-parties"

    # Generate participant sessions
    python scripts/exploration_study_admin.py create-sessions \
        --study-id "abc123" \
        --count 20

    # List sessions with URLs
    python scripts/exploration_study_admin.py list-sessions --study-id "abc123"

    # Export data
    python scripts/exploration_study_admin.py export --study-id "abc123" --format json

Note: Topics (klimaschutz, soziale-gerechtigkeit), task duration (600s), and parties
      are hardcoded in src/exploration_study/models/study.py
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Initialize Firebase before importing modules that use it
from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.models.session import get_conditions_for_group  # noqa: E402
from src.exploration_study.models.study import StudyConfig  # noqa: E402
from src.exploration_study.services.counterbalancer import get_counterbalancer  # noqa: E402
from src.exploration_study.services.session_repository import get_session_repository  # noqa: E402
from src.exploration_study.services.study_repository import get_study_repository  # noqa: E402


async def create_study(args: argparse.Namespace) -> None:
    """Create a new study."""
    study_repo = get_study_repository()

    config = StudyConfig(context_id=args.context_id)

    study = await study_repo.create_study(name=args.name, config=config)

    print("\nStudy created successfully!")
    print(f"  ID: {study.id}")
    print(f"  Name: {study.name}")
    print(f"  Status: {study.status}")
    print(f"  Context: {config.context_id}")
    print(f"  Topics: {', '.join(config.topics)}")
    print(f"  Parties: {', '.join(config.parties)}")
    print(f"  Task Duration: {config.task_duration_seconds}s")


async def list_studies(args: argparse.Namespace) -> None:
    """List all studies."""
    study_repo = get_study_repository()
    session_repo = get_session_repository()

    studies = await study_repo.list_studies()

    if not studies:
        print("No studies found.")
        return

    print(f"\nFound {len(studies)} studies:\n")

    for study in studies:
        sessions = await session_repo.list_sessions_for_study(study.id)
        completed = sum(
            1
            for s in sessions
            if (s.state.value if hasattr(s.state, "value") else s.state) == "complete"
        )

        print(f"  {study.id}")
        print(f"    Name: {study.name}")
        print(f"    Status: {study.status}")
        print(f"    Sessions: {len(sessions)} ({completed} completed)")
        print(f"    Created: {study.created_at.strftime('%Y-%m-%d %H:%M')}")
        print()


async def get_study(args: argparse.Namespace) -> None:
    """Get details of a specific study."""
    study_repo = get_study_repository()
    session_repo = get_session_repository()

    study = await study_repo.get_study(args.study_id)
    if not study:
        print(f"Study not found: {args.study_id}")
        return

    sessions = await session_repo.list_sessions_for_study(study.id)

    print("\nStudy Details:")
    print(f"  ID: {study.id}")
    print(f"  Name: {study.name}")
    print(f"  Status: {study.status}")
    print(f"  Context ID: {study.config.context_id}")
    print(f"  Topics: {', '.join(study.config.topics)}")
    print(f"  Parties: {', '.join(study.config.parties)}")
    print(f"  Task Duration: {study.config.task_duration_seconds}s")
    print(f"  Created: {study.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Updated: {study.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nSessions: {len(sessions)}")

    # Count by state and group
    by_state: dict[str, int] = {}
    by_group: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for s in sessions:
        state = s.state.value if hasattr(s.state, "value") else str(s.state)
        by_state[state] = by_state.get(state, 0) + 1
        by_group[s.group] = by_group.get(s.group, 0) + 1

    print(f"  By state: {by_state}")
    print(f"  By group: {by_group}")


async def update_study(args: argparse.Namespace) -> None:
    """Update a study."""
    study_repo = get_study_repository()

    study = await study_repo.get_study(args.study_id)
    if not study:
        print(f"Study not found: {args.study_id}")
        return

    updates = {}
    if args.name:
        updates["name"] = args.name
    if args.status:
        updates["status"] = args.status

    if not updates:
        print("No updates specified.")
        return

    updated_study = await study_repo.update_study(args.study_id, updates)
    if not updated_study:
        print(f"Failed to update study: {args.study_id}")
        return
    print(f"Study updated: {updated_study.id}")
    print(f"  Name: {updated_study.name}")
    print(f"  Status: {updated_study.status}")


async def create_sessions(args: argparse.Namespace) -> None:
    """Create participant sessions for a study."""
    study_repo = get_study_repository()
    session_repo = get_session_repository()
    counterbalancer = get_counterbalancer()

    study = await study_repo.get_study(args.study_id)
    if not study:
        print(f"Study not found: {args.study_id}")
        return

    print(f"\nCreating {args.count} sessions for study: {study.name}")

    session_ids = []
    for i in range(args.count):
        group = await counterbalancer.assign_group(args.study_id)
        conditions = get_conditions_for_group(group, study.config.topics)

        session = await session_repo.create_session(
            study_id=args.study_id,
            group=group,
            conditions=conditions,
        )
        session_ids.append(session.id)
        print(f"  Created session {i + 1}/{args.count}: {session.id} (Group {group})")

    group_counts = await counterbalancer.get_group_counts(args.study_id)

    print(f"\nCreated {len(session_ids)} sessions")
    print(f"  Group A: {group_counts.get('A', 0)}")
    print(f"  Group B: {group_counts.get('B', 0)}")
    print(f"  Group C: {group_counts.get('C', 0)}")
    print(f"  Group D: {group_counts.get('D', 0)}")

    if args.output:
        with open(args.output, "w") as f:
            for sid in session_ids:
                f.write(f"{sid}\n")
        print(f"\nSession IDs written to: {args.output}")


async def list_sessions(args: argparse.Namespace) -> None:
    """List sessions for a study."""
    study_repo = get_study_repository()
    session_repo = get_session_repository()

    study = await study_repo.get_study(args.study_id)
    if not study:
        print(f"Study not found: {args.study_id}")
        return

    sessions = await session_repo.list_sessions_for_study(args.study_id)

    if not sessions:
        print("No sessions found.")
        return

    base_url = args.base_url or os.getenv("STUDY_BASE_URL", "http://localhost:3000")

    print(f"\nSessions for study: {study.name}")
    print(f"Total: {len(sessions)}\n")

    for session in sessions:
        state = (
            session.state.value
            if hasattr(session.state, "value")
            else str(session.state)
        )
        url = f"{base_url}/study/{session.id}"

        status_icon = "✓" if state == "complete" else "▶" if state != "created" else "○"

        print(f"  {status_icon} {session.id}")
        print(f"      Group: {session.group} | State: {state}")
        print(f"      URL: {url}")
        if session.started_at:
            print(f"      Started: {session.started_at.strftime('%Y-%m-%d %H:%M')}")
        if session.completed_at:
            print(f"      Completed: {session.completed_at.strftime('%Y-%m-%d %H:%M')}")
        print()


async def export_data(args: argparse.Namespace) -> None:
    """Export study data."""
    study_repo = get_study_repository()
    session_repo = get_session_repository()

    study = await study_repo.get_study(args.study_id)
    if not study:
        print(f"Study not found: {args.study_id}")
        return

    sessions = await session_repo.list_sessions_for_study(args.study_id)

    if args.format == "json":
        export_data = {
            "study": study.model_dump(mode="json"),
            "sessions": [s.model_dump(mode="json") for s in sessions],
        }

        output_file = args.output or f"study_{args.study_id}_export.json"
        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"Exported to: {output_file}")

    elif args.format == "csv":
        import csv

        output_file = args.output or f"study_{args.study_id}_export.csv"

        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "session_id",
                    "group",
                    "state",
                    "created_at",
                    "started_at",
                    "completed_at",
                    "condition_1_system",
                    "condition_1_topic",
                    "condition_2_system",
                    "condition_2_topic",
                    "preferred_system",
                    "preference_strength",
                ]
            )

            for session in sessions:
                cond_1 = session.conditions.get("1")
                cond_2 = session.conditions.get("2")
                prefs = session.participant_data.preferences

                state = (
                    session.state.value
                    if hasattr(session.state, "value")
                    else str(session.state)
                )

                writer.writerow(
                    [
                        session.id,
                        session.group,
                        state,
                        session.created_at.isoformat() if session.created_at else "",
                        session.started_at.isoformat() if session.started_at else "",
                        session.completed_at.isoformat()
                        if session.completed_at
                        else "",
                        cond_1.system.value if cond_1 else "",
                        cond_1.topic if cond_1 else "",
                        cond_2.system.value if cond_2 else "",
                        cond_2.topic if cond_2 else "",
                        prefs.preferred_system.value if prefs.preferred_system else "",
                        prefs.preference_strength or "",
                    ]
                )

        print(f"Exported to: {output_file}")


async def delete_session(args: argparse.Namespace) -> None:
    """Delete a session."""
    session_repo = get_session_repository()

    if not args.force:
        confirm = input(f"Delete session {args.session_id}? [y/N]: ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    deleted = await session_repo.delete_session(args.session_id)
    if deleted:
        print(f"Deleted session: {args.session_id}")
    else:
        print(f"Session not found: {args.session_id}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Exploration Study Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create-study
    create_study_parser = subparsers.add_parser(
        "create-study", help="Create a new study"
    )
    create_study_parser.add_argument("--name", required=True, help="Study name")
    create_study_parser.add_argument(
        "--context-id", required=True, help="Context ID for fake parties"
    )

    # list-studies
    subparsers.add_parser("list-studies", help="List all studies")

    # get-study
    get_study_parser = subparsers.add_parser("get-study", help="Get study details")
    get_study_parser.add_argument("--study-id", required=True, help="Study ID")

    # update-study
    update_study_parser = subparsers.add_parser("update-study", help="Update a study")
    update_study_parser.add_argument("--study-id", required=True, help="Study ID")
    update_study_parser.add_argument("--name", help="New study name")
    update_study_parser.add_argument(
        "--status",
        choices=["draft", "active", "completed"],
        help="New status",
    )

    # create-sessions
    create_sessions_parser = subparsers.add_parser(
        "create-sessions", help="Create participant sessions"
    )
    create_sessions_parser.add_argument("--study-id", required=True, help="Study ID")
    create_sessions_parser.add_argument(
        "--count", type=int, required=True, help="Number of sessions to create"
    )
    create_sessions_parser.add_argument("--output", help="Output file for session IDs")

    # list-sessions
    list_sessions_parser = subparsers.add_parser(
        "list-sessions", help="List sessions for a study"
    )
    list_sessions_parser.add_argument("--study-id", required=True, help="Study ID")
    list_sessions_parser.add_argument(
        "--base-url", help="Base URL for participant links"
    )

    # export
    export_parser = subparsers.add_parser("export", help="Export study data")
    export_parser.add_argument("--study-id", required=True, help="Study ID")
    export_parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Export format"
    )
    export_parser.add_argument("--output", help="Output file path")

    # delete-session
    delete_session_parser = subparsers.add_parser(
        "delete-session", help="Delete a session"
    )
    delete_session_parser.add_argument("--session-id", required=True, help="Session ID")
    delete_session_parser.add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Map commands to functions
    commands = {
        "create-study": create_study,
        "list-studies": list_studies,
        "get-study": get_study,
        "update-study": update_study,
        "create-sessions": create_sessions,
        "list-sessions": list_sessions,
        "export": export_data,
        "delete-session": delete_session,
    }

    command_func = commands.get(args.command)
    if command_func:
        asyncio.run(command_func(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
