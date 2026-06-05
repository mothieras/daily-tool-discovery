from daily_tool_discovery import __version__


def test_package_has_version():
    assert __version__ == "0.1.0"


def test_cli_main_is_callable():
    from daily_tool_discovery.cli import main

    assert main([]) == 0
