"""Unit tests for the <gen> secret macro (pure, no Mongo/Textual)."""

import re

import pytest

from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.secret_macro import (
    DEFAULT_GENERATED_LENGTH,
    expand_secret_macros,
    random_token,
)

TOKEN_RE = r"[A-Za-z0-9]"


def test_default_length_is_32():
    assert DEFAULT_GENERATED_LENGTH == 32
    assert re.fullmatch(TOKEN_RE + "{32}", random_token())


def test_bare_gen_expands_to_default_length():
    out = expand_secret_macros({"flag": "<gen>"})
    assert re.fullmatch(TOKEN_RE + "{32}", out["flag"])


def test_custom_length():
    out = expand_secret_macros({"flag": "<gen:16>"})
    assert re.fullmatch(TOKEN_RE + "{16}", out["flag"])


def test_composes_inline():
    out = expand_secret_macros({"flag": "FLAG{<gen>}"})
    assert re.fullmatch(r"FLAG\{" + TOKEN_RE + r"{32}\}", out["flag"])


def test_each_occurrence_gets_fresh_randomness():
    out = expand_secret_macros({"flag": "<gen:20>-<gen:20>"})
    first, second = out["flag"].split("-")
    assert first != second and len(first) == len(second) == 20


def test_values_without_macro_pass_through():
    secrets = {"flag": "FLAG{static}", "note": "keep <genuine> text"}
    assert expand_secret_macros(secrets) == secrets


def test_out_of_range_length_raises():
    with pytest.raises(AdminError):
        expand_secret_macros({"flag": "<gen:0>"})
    with pytest.raises(AdminError):
        expand_secret_macros({"flag": "<gen:999>"})


def test_input_dict_is_not_mutated():
    secrets = {"flag": "<gen>"}
    expand_secret_macros(secrets)
    assert secrets == {"flag": "<gen>"}
