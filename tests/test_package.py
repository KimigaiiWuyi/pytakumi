"""Package metadata and public export surface."""

from __future__ import annotations

import pytakumi


def test_version_semver_shape():
    parts = pytakumi.__version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])


def test_public_exports_match_all():
    for name in pytakumi.__all__:
        assert hasattr(pytakumi, name), name
        assert getattr(pytakumi, name) is not None


def test_high_level_api_exported():
    assert callable(pytakumi.html_to_pic)
    assert callable(pytakumi.text_to_pic)
    assert callable(pytakumi.md_to_pic)
    assert callable(pytakumi.render_markdown)


def test_unknown_attr_raises():
    try:
        _ = pytakumi.this_does_not_exist  # type: ignore[attr-defined]
        raise AssertionError("expected AttributeError")
    except AttributeError as e:
        assert "this_does_not_exist" in str(e)
