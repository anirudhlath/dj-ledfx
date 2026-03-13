from __future__ import annotations

import sys


def test_profile_flag_default_is_none() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile is None
    finally:
        sys.argv = orig


def test_profile_flag_no_value_gives_sampling() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--profile"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile == "sampling"
    finally:
        sys.argv = orig


def test_profile_flag_deep() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--profile", "deep"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile == "deep"
    finally:
        sys.argv = orig


def test_metrics_flag_default_false() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics is False
    finally:
        sys.argv = orig


def test_metrics_flag_enabled() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--metrics"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics is True
        assert args.metrics_port == 9091
    finally:
        sys.argv = orig


def test_metrics_port_custom() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--metrics", "--metrics-port", "8080"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics_port == 8080
    finally:
        sys.argv = orig
