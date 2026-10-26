from inventory.create_group import create_group as _create_group, update_group as _update_group


def create_group(page, Config):
    # "Run Create" / "Run Update" are sub-options of the Create Group module (run_create_group / run_update_group).
    # The group values come with the run: the UI's Create Group page, or backend/Config.py for CLI runs.
    if getattr(Config, "run_create_group", False):
        _create_group(page, Config)
    if getattr(Config, "run_update_group", False):
        _update_group(page, Config)


__all__ = ["create_group"]
