from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from pydantic import ValidationError

from videos_llm.application.composition_service import (
    CompositionError,
    render_composition,
    resolve_composition,
)
from videos_llm.application.production_service import (
    MediaImportError,
    import_media,
    select_asset,
)
from videos_llm.domain.production import SelectionRole
from videos_llm.infrastructure.compositor import RenderError
from videos_llm.infrastructure.production_store import ProductionStoreError
from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videos-llm",
        description="Local scene-driven short-video production workflow.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a project")
    validate.add_argument("project")
    validate.add_argument(
        "--production",
        action="store_true",
        help="also resolve production selections and composition",
    )

    production = commands.add_parser(
        "production",
        help="import and select scene media",
    )
    production_commands = production.add_subparsers(
        dest="production_command",
        required=True,
    )
    import_command = production_commands.add_parser(
        "import",
        help="import one local media file",
    )
    import_command.add_argument("project")
    import_command.add_argument("scene")
    import_command.add_argument("media")
    import_command.add_argument("--method", default="manual")
    import_command.add_argument("--provider")
    import_command.add_argument("--model")
    import_command.add_argument("--prompt")
    import_command.add_argument("--notes")

    select = production_commands.add_parser(
        "select",
        help="select one imported asset for a scene role",
    )
    select.add_argument("project")
    select.add_argument("scene")
    select.add_argument("role", choices=[role.value for role in SelectionRole])
    select.add_argument("asset")

    compose = commands.add_parser("compose", help="render an MP4")
    compose.add_argument("project")
    compose.add_argument("--preview", action="store_true")
    compose.add_argument("--output")
    compose.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "validate":
            loaded = load_project(arguments.project)
            if arguments.production:
                resolve_composition(arguments.project)
                print(f"valid production project: {loaded.project.id}")
            else:
                print(f"valid creative project: {loaded.project.id}")
            return 0

        if arguments.command == "production":
            if arguments.production_command == "import":
                result = import_media(
                    arguments.project,
                    arguments.scene,
                    arguments.media,
                    method=arguments.method,
                    provider=arguments.provider,
                    model=arguments.model,
                    prompt_path=arguments.prompt,
                    notes=arguments.notes,
                )
                print(
                    f"imported {result.asset.id} -> {result.asset.path} "
                    f"(attempt {result.attempt.id})"
                )
                return 0

            selected = select_asset(
                arguments.project,
                arguments.scene,
                arguments.role,
                arguments.asset,
            )
            print(
                f"selected {arguments.role}: "
                f"{selected.selections[SelectionRole(arguments.role)]}"
            )
            return 0

        output = render_composition(
            arguments.project,
            preview=arguments.preview,
            output_path=arguments.output,
            overwrite=arguments.overwrite,
        )
        print(f"rendered {output}")
        return 0
    except (
        CompositionError,
        MediaImportError,
        ProductionStoreError,
        ProjectValidationError,
        RenderError,
        ValidationError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def entrypoint() -> NoReturn:
    raise SystemExit(main())
