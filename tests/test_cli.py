import pytest
import sys
from sven.cli import build_parser

def test_build_parser_install():
    parser = build_parser()
    args = parser.parse_args(["--root", "/tmp", "install", "neovim"])
    assert args.command == "install"
    assert args.packages == ["neovim"]
    assert args.root == "/tmp"

def test_build_parser_upgrade():
    parser = build_parser()
    args = parser.parse_args(["upgrade"])
    assert args.command == "upgrade"
    assert not args.packages

def test_build_parser_search():
    parser = build_parser()
    args = parser.parse_args(["search", "foo"])
    assert args.command == "search"
    assert args.query == "foo"

def test_build_parser_flags():
    parser = build_parser()
    args = parser.parse_args(["--no-color", "--dry-run", "install", "foo", "--source"])
    assert args.no_color is True
    assert args.dry_run is True
    assert args.source is True
