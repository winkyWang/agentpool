"""Tests for project file-watcher filtering."""

from pathlib import Path

from watchfiles import Change

from agentpool.utils.file_watcher import FileWatcher
from agentpool_server.opencode_server.models.config import DEFAULT_IGNORE
from agentpool_server.opencode_server.server import (
    _should_ignore_watched_path,
    _watcher_ignore_patterns,
)


def test_default_watcher_ignores_runtime_logs() -> None:
    """The project watcher must not observe its own runtime log directory."""
    assert "logs/**" in DEFAULT_IGNORE


def test_default_watcher_still_allows_source_files() -> None:
    """Runtime exclusions must not suppress ordinary source changes."""
    source_path = Path("src") / "package" / "module.py"
    assert not any(source_path.match(pattern) for pattern in DEFAULT_IGNORE)


def test_file_watcher_filters_changes_before_dispatch() -> None:
    """Ignored self-generated log writes never reach logging or callbacks."""

    async def callback(changes: set[tuple[Change, str]]) -> None:
        del changes

    watcher = FileWatcher(
        paths=["."],
        callback=callback,
        path_filter=lambda path: not path.endswith(".log"),
    )
    selected = watcher._select_changes(
        {
            (Change.modified, "/project/logs/runtime.log"),
            (Change.modified, "/project/src/module.py"),
        }
    )
    assert selected == {(Change.modified, "/project/src/module.py")}
    assert not watcher._watchfiles_filter(
        Change.modified,
        "/project/logs/runtime.log",
    )
    assert watcher._watchfiles_filter(
        Change.modified,
        "/project/src/module.py",
    )


def test_runtime_defaults_exist_before_public_config_is_requested() -> None:
    """Startup cannot depend on a later request to initialize watcher defaults."""
    patterns = _watcher_ignore_patterns(None)
    assert "logs/**" in patterns
    assert _should_ignore_watched_path(
        "/project/logs/runtime.log",
        working_dir="/project",
        ignore_patterns=patterns,
    )
