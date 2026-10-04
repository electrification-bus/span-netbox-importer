import json
from types import SimpleNamespace

import pytest
import requests

PEM = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"


@pytest.fixture
def auth_file(tmp_path, monkeypatch):
    path = tmp_path / "span-auth.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "default_panel": "nt-0000-abcde",
                "panels": {"nt-0000-abcde": {"hostname": "span-nt-0000-abcde.local", "ebus_broker_password": "pw"}},
            }
        )
    )
    path.chmod(0o600)
    monkeypatch.setenv("SPAN_AUTH_FILE", str(path))
    return path


def test_credentials(importer, auth_file):
    assert importer.list_panels() == ["nt-0000-abcde"]
    assert importer.get_panel_credentials("nt-0000-abcde")["ebus_broker_password"] == "pw"
    assert importer.get_panel_credentials("nt-9999-zzzzz") is None


def test_missing_auth_file(importer, tmp_path, monkeypatch):
    monkeypatch.setenv("SPAN_AUTH_FILE", str(tmp_path / "absent.json"))
    assert importer.list_panels() == []


def test_insecure_auth_file_warns(importer, auth_file, capsys):
    auth_file.chmod(0o644)
    importer.load_auth_file()
    assert "insecure permissions" in capsys.readouterr().err


def ca_setup(importer, tmp_path, monkeypatch, response_text):
    monkeypatch.setenv("SPAN_CA_CERT_DIR", str(tmp_path / "certs"))
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return SimpleNamespace(text=response_text, raise_for_status=lambda: None)

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


def test_ca_downloaded_then_cached(importer, tmp_path, monkeypatch):
    calls = ca_setup(importer, tmp_path, monkeypatch, PEM)
    monkeypatch.setattr(importer, "cert_expiring", lambda path: False)
    path = importer.ensure_ca_cert("nt-0000-abcde", "span-nt-0000-abcde.local")
    assert path == tmp_path / "certs" / "nt-0000-abcde.crt"
    assert path.read_text() == PEM
    assert calls == ["http://span-nt-0000-abcde.local/api/v2/certificate/ca"]
    importer.ensure_ca_cert("nt-0000-abcde", "span-nt-0000-abcde.local")
    assert len(calls) == 1


def test_expiring_ca_is_refreshed(importer, tmp_path, monkeypatch):
    calls = ca_setup(importer, tmp_path, monkeypatch, PEM)
    (tmp_path / "certs").mkdir()
    (tmp_path / "certs" / "nt-0000-abcde.crt").write_text("old")
    monkeypatch.setattr(importer, "cert_expiring", lambda path: True)
    assert importer.ensure_ca_cert("nt-0000-abcde", "h").read_text() == PEM
    assert len(calls) == 1


def test_non_pem_ca_is_rejected(importer, tmp_path, monkeypatch):
    ca_setup(importer, tmp_path, monkeypatch, "<html>login</html>")
    with pytest.raises(ValueError):
        importer.ensure_ca_cert("nt-0000-abcde", "h")
    assert not (tmp_path / "certs" / "nt-0000-abcde.crt").exists()


@pytest.mark.parametrize(
    ("name", "serial"),
    [
        ("span-nt-2143-c1akc-EBUS._ebus._tcp.local.", "nt-2143-c1akc"),
        ("SPAN-nt-2143-c1akc-ebus._ebus._tcp.local.", "nt-2143-c1akc"),
        ("other-device._ebus._tcp.local.", None),
        ("span-nt-2143-c1akc-HTTP._ebus._tcp.local.", None),
        ("span--EBUS._ebus._tcp.local.", None),
    ],
)
def test_serial_from_instance(importer, name, serial):
    assert importer.serial_from_instance(name) == serial


@pytest.mark.parametrize("content", ["{not json", "[]", '{"panels": null}'])
def test_malformed_auth_file(importer, tmp_path, monkeypatch, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    path.chmod(0o600)
    monkeypatch.setenv("SPAN_AUTH_FILE", str(path))
    assert importer.list_panels() == []
    assert importer.get_panel_credentials("x") is None
