import importlib
import sys


def load_module_with_tty(monkeypatch, is_tty: bool):
    class FakeStdout:
        def isatty(self):
            return is_tty

    monkeypatch.setattr(sys, "stdout", FakeStdout())

    import sys_infra.utils

    importlib.reload(sys_infra.utils)

    return sys_infra.utils


def test_supports_color_true(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod._supports_color() is True


def test_supports_color_false(monkeypatch):
    mod = load_module_with_tty(monkeypatch, False)
    assert mod._supports_color() is False


def test_c_applies_color_when_enabled(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    result = mod._c("32", "hello")
    assert result == "\033[32mhello\033[0m"


def test_c_returns_plain_text_when_disabled(monkeypatch):
    mod = load_module_with_tty(monkeypatch, False)
    result = mod._c("32", "hello")
    assert result == "hello"


def test_green(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.green("x") == "\033[32mx\033[0m"


def test_red(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.red("x") == "\033[31;1mx\033[0m"


def test_yellow(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.yellow("x") == "\033[33mx\033[0m"


def test_cyan(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.cyan("x") == "\033[36mx\033[0m"


def test_bold(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.bold("x") == "\033[1mx\033[0m"


def test_dim(monkeypatch):
    mod = load_module_with_tty(monkeypatch, True)
    assert mod.dim("x") == "\033[2mx\033[0m"


def test_all_colors_disabled_return_plain_text(monkeypatch):
    mod = load_module_with_tty(monkeypatch, False)

    funcs = [
        mod.green,
        mod.red,
        mod.yellow,
        mod.cyan,
        mod.bold,
        mod.dim,
    ]

    for f in funcs:
        assert f("hello") == "hello"
