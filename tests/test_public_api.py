from __future__ import annotations


def test_config_path_resolver_is_available_from_root_package() -> None:
    """Consumers should not need to initialize config internals directly."""
    from wolfharness import resolve_config_path

    assert callable(resolve_config_path)
