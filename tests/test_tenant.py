"""Tests for request-scoped tenant context."""

from sunnyware import tenant


def test_default_empty():
    tenant.reset()
    assert tenant.get_key() == ""


def test_set_get():
    tenant.set_key("abc")
    assert tenant.get_key() == "abc"


def test_reset_clears():
    tenant.set_key("xyz")
    tenant.reset()
    assert tenant.get_key() == ""


def test_set_none_yields_empty():
    tenant.set_key(None)
    assert tenant.get_key() == ""


def test_set_empty_string():
    tenant.set_key("")
    assert tenant.get_key() == ""
