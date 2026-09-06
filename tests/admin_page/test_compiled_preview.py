"""Unit tests for the compiled-preview renderer (pure, no Mongo/Textual)."""

from fit_ctf_admin.scenario.compiled_preview import (
    build_preview_param_map,
    render_compiled_preview,
)

TEMPLATE = """---
name: "{{ project_name }}_{{ username }}_demo"

services:
  web:
    build:
      context: {{ paths__modules }}/template
    networks:
      {{ network_map__shared }}:
    ports:
      - "{{ web__port_map__http }}:80"
    environment:
      - "ADMIN={{ web__env_map__ADMIN }}"
      - "MODE={{ run_mode }}"
    volumes:
      - "{{ web__volume_map__cfg }}:/cfg:ro"
"""

RAW = {
    "secrets": {"flag_main": "FLAG{x}"},
    "service_configs": {
        "web": {
            "env_map": {"ADMIN": "root"},
            "port_map": {"http": 8080},
            "volume_map": {"cfg": {"src_path": "/tmp/cfg", "template_params": {}}},
        }
    },
    "config_params": {"run_mode": "hard"},
}


def test_values_are_substituted():
    out = render_compiled_preview(TEMPLATE, RAW)
    assert "8080:80" in out
    assert "ADMIN=root" in out
    assert "MODE=hard" in out
    assert "/tmp/cfg:/cfg:ro" in out


def test_compile_supplied_variables_use_placeholders():
    out = render_compiled_preview(TEMPLATE, RAW)
    assert "<project>_<user>_demo" in out
    assert "<paths:modules>/template" in out
    assert "<shared_net>:" in out


def test_missing_value_yields_readable_error():
    raw = {"secrets": {}, "service_configs": {}, "config_params": {}}
    out = render_compiled_preview(TEMPLATE, raw)
    assert out.startswith("# Cannot render preview")
    assert "web__port_map__http" in out


def test_template_syntax_error_yields_readable_error():
    out = render_compiled_preview("{% broken", RAW)
    assert out.startswith("# Cannot render preview — template error")


def test_param_map_naming_matches_compiler_convention():
    params = build_preview_param_map(RAW)
    assert params["web__env_map__ADMIN"] == "root"
    assert params["web__port_map__http"] == 8080
    assert params["web__volume_map__cfg"] == "/tmp/cfg"
    assert params["run_mode"] == "hard"
    assert params["project_name"] == "<project>"
