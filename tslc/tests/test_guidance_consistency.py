"""Repository guidance and task-skill routing stay executable and honest."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
import re
import shlex


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_GUIDANCE_PATHS = (
    _REPO_ROOT / "AGENTS.md",
    _REPO_ROOT / "PLANS.md",
    _REPO_ROOT / "tslc" / "AGENTS.md",
    _REPO_ROOT / "tsldata" / "AGENTS.md",
)
_SKILL_REFERENCE_RE = re.compile(
    r"\.agents/skills/(?P<name>[a-z0-9-]+)/SKILL\.md"
)
_TEST_PATH_RE = re.compile(r"tslc/tests/test_[A-Za-z0-9_.*?\[\]-]+\.py")


def _skill_paths() -> tuple[Path, ...]:
    return tuple(sorted(_SKILLS_ROOT.glob("*/SKILL.md")))


def _guidance_paths() -> tuple[Path, ...]:
    return (*_GUIDANCE_PATHS, *_skill_paths())


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    try:
        header = text.split("---\n", 2)[1]
    except IndexError as error:  # pragma: no cover - assertion message path
        raise AssertionError(f"unterminated frontmatter: {path}") from error
    fields: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _quoted_yaml_field(path: Path, key: str) -> str:
    match = re.search(
        rf'^\s*{re.escape(key)}:\s*"(?P<value>[^"]+)"\s*$',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match is not None, f"missing quoted {key}: {path}"
    return match.group("value")


def _bash_commands(text: str) -> Iterable[str]:
    in_bash_fence = False
    pending = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not in_bash_fence:
            in_bash_fence = stripped == "```bash"
            continue
        if stripped == "```":
            if pending:
                yield pending
            in_bash_fence = False
            pending = ""
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        command = pending + stripped
        pending = ""
        yield command


def _is_module_wide_generated_test(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytestmark"
            for target in node.targets
        ):
            continue
        if any(
            isinstance(child, ast.Attribute) and child.attr == "generated_build"
            for child in ast.walk(node.value)
        ):
            return True
    return False


def test_skill_routes_resolve() -> None:
    canonical = {path.parent.name: path for path in _skill_paths()}
    root_guidance = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    routed = {
        match.group("name") for match in _SKILL_REFERENCE_RE.finditer(root_guidance)
    }

    assert routed == set(canonical), {
        "missing_routes": sorted(set(canonical) - routed),
        "unknown_routes": sorted(routed - set(canonical)),
    }
    for guidance_path in _GUIDANCE_PATHS:
        text = guidance_path.read_text(encoding="utf-8")
        for match in _SKILL_REFERENCE_RE.finditer(text):
            referenced = _REPO_ROOT / match.group(0)
            assert referenced.is_file(), (
                f"missing skill referenced by {guidance_path}: {referenced}"
            )


def test_skill_metadata_matches_directory() -> None:
    for skill_path in _skill_paths():
        fields = _frontmatter(skill_path)
        name = fields.get("name")
        assert name == skill_path.parent.name, skill_path
        assert fields.get("description"), f"missing description: {skill_path}"
        assert "TODO" not in skill_path.read_text(encoding="utf-8"), skill_path

        metadata = skill_path.parent / "agents" / "openai.yaml"
        assert metadata.is_file(), metadata
        assert _quoted_yaml_field(metadata, "display_name")
        short_description = _quoted_yaml_field(metadata, "short_description")
        assert 25 <= len(short_description) <= 64, metadata
        default_prompt = _quoted_yaml_field(metadata, "default_prompt")
        assert f"${name}" in default_prompt, metadata

        bridge = _REPO_ROOT / ".claude" / "skills" / str(name)
        assert bridge.is_symlink(), bridge
        assert bridge.resolve() == skill_path.parent.resolve(), bridge


def test_guidance_test_paths_resolve() -> None:
    for guidance_path in _guidance_paths():
        text = guidance_path.read_text(encoding="utf-8")
        for pattern in sorted(set(_TEST_PATH_RE.findall(text))):
            matches = tuple(_REPO_ROOT.glob(pattern))
            assert matches, f"unresolved test path in {guidance_path}: {pattern}"
            assert all(path.is_file() for path in matches), (guidance_path, pattern)


def test_generated_test_commands_are_honest() -> None:
    for guidance_path in _guidance_paths():
        text = guidance_path.read_text(encoding="utf-8")
        for command in _bash_commands(text):
            if "pytest" not in command:
                continue
            tokens = shlex.split(command)
            test_paths = tuple(
                _REPO_ROOT / token
                for token in tokens
                if token.startswith("tslc/tests/test_")
                and token.endswith(".py")
                and not any(marker in token for marker in "*?[")
            )
            generated_paths = tuple(
                path
                for path in test_paths
                if path.is_file() and _is_module_wide_generated_test(path)
            )
            has_generated_flag = "--run-generated-builds" in tokens

            assert not generated_paths or has_generated_flag, (
                f"generated tests silently skip in {guidance_path}: {command}"
            )
            if has_generated_flag and test_paths:
                assert generated_paths, (
                    f"generated-test flag selects no generated module in "
                    f"{guidance_path}: {command}"
                )
