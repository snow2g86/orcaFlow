"""AuditSink — append-only, 시크릿 스크러빙, 해시 체인."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca_core.audit import (
    AuditSink,
    AuditWriteError,
    build_audit_log,
    compute_hash,
    scrub_mapping,
    verify_chain,
)
from orca_core.audit.scrub import mask_home_path, mask_url_secrets
from orca_core.schema import AuditLog


@pytest.fixture
def sink_path(tmp_path: Path) -> Path:
    return tmp_path / "logs" / "audit.log"


async def test_record_writes_jsonl_and_returns_audit_log(sink_path: Path):
    sink = AuditSink(log_path=sink_path)
    entry = await sink.record(
        actor="user",
        action="fs.delete",
        target="/tmp/x",
        status="success",
        policy_decision="allow",
        run_id="r1",
        run_step_id="s1",
    )
    assert isinstance(entry, AuditLog)
    assert sink_path.exists()
    line = sink_path.read_text().strip()
    payload = json.loads(line)
    assert payload["actor"] == "user"
    assert payload["action"] == "fs.delete"
    assert payload["hash_self"] is not None


async def test_record_raises_on_db_failure(sink_path: Path):
    class BadWriter:
        async def insert(self, record):  # type: ignore[no-untyped-def]
            raise RuntimeError("db down")

    sink = AuditSink(log_path=sink_path, db_writer=BadWriter())
    with pytest.raises(AuditWriteError):
        await sink.record(
            actor="user",
            action="fs.delete",
            target="/tmp/x",
            status="success",
            policy_decision="allow",
            run_id="r",
            run_step_id="s",
        )
    # No file line should have been written because DB failure comes first
    assert not sink_path.exists()


async def test_record_hash_chain_provider(sink_path: Path):
    previous: list[str | None] = [None]

    async def provider() -> str | None:
        return previous[0]

    sink = AuditSink(log_path=sink_path, hash_prev_provider=provider)

    first = await sink.record(
        actor="a",
        action="fs.delete",
        target="/x",
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s1",
    )
    previous[0] = first.hash_self

    second = await sink.record(
        actor="a",
        action="fs.delete",
        target="/y",
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s2",
    )
    assert second.hash_prev == first.hash_self

    result = verify_chain([first, second])
    assert result.ok


def test_verify_chain_detects_tamper():
    a = build_audit_log(
        actor="x",
        action="fs.delete",
        target="/a",
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s1",
    )
    b = build_audit_log(
        actor="x",
        action="fs.delete",
        target="/b",
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s2",
        hash_prev=a.hash_self,
    )

    # Tamper with b by constructing a new one with swapped hash_self
    tampered = b.model_copy(update={"hash_self": "deadbeef"})
    result = verify_chain([a, tampered])
    assert not result.ok
    assert result.broken_at == tampered.id


def test_scrub_mapping_masks_secrets():
    payload = {
        "api_key": "sk-secret",
        "token": "abcdef",
        "nested": {"password": "pw", "ok": "safe"},
        "list": [{"bearer": "xyz"}, "plain"],
    }
    scrubbed = scrub_mapping(payload)
    assert scrubbed["api_key"] == "***"
    assert scrubbed["token"] == "***"
    assert scrubbed["nested"]["password"] == "***"
    assert scrubbed["nested"]["ok"] == "safe"
    assert scrubbed["list"][0]["bearer"] == "***"
    assert scrubbed["list"][1] == "plain"


def test_mask_free_text_secrets_bearer_jwt_sk_and_kv():
    """H1 regression: free-text body scrubber covers Bearer, JWT, sk-…
    and `"key":"value"` patterns.
    """
    from orca_core.audit.scrub import mask_free_text_secrets

    text = (
        "Authorization: Bearer ABCDEF1234567890\n"
        'token="myverysecretvalue123"\n'
        "key=sk-realsecret123456 pk-otherleak4567890\n"
        "jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcXYZ-_\n"
        '{"password": "plaintextpw", "ok": true}'
    )
    masked = mask_free_text_secrets(text)
    for leaked in (
        "ABCDEF1234567890",
        "myverysecretvalue123",
        "sk-realsecret123456",
        "pk-otherleak4567890",
        "eyJhbGciOiJIUzI1NiJ9",
        "plaintextpw",
    ):
        assert leaked not in masked, f"{leaked!r} not scrubbed"
    # Empty string unchanged
    assert mask_free_text_secrets("") == ""


async def test_sink_scrubs_path_and_secrets_in_mirror(sink_path: Path, monkeypatch, tmp_path: Path):
    # Ensure the audit file mirror masks HOME
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    sink = AuditSink(log_path=sink_path)
    await sink.record(
        actor="u",
        action="fs.delete",
        target=str(fake_home / "docs" / "secret.txt"),
        status="success",
        policy_decision="allow",
        run_id="r",
        run_step_id="s",
    )
    line = sink_path.read_text().strip()
    payload = json.loads(line)
    assert payload["target"].startswith("~/")


def test_mask_home_path_noop_when_not_home(tmp_path: Path):
    # /etc is outside HOME → unchanged
    assert mask_home_path("/etc/hosts") == "/etc/hosts"


def test_mask_url_secrets_masks_known_params():
    url = "https://api.example.com/v1/x?token=abcdef&normal=ok&api_key=sk-secret&q=hello"
    masked = mask_url_secrets(url)
    assert "token=%2A%2A%2A" in masked or "token=***" in masked
    assert "api_key=%2A%2A%2A" in masked or "api_key=***" in masked
    assert "normal=ok" in masked
    assert "q=hello" in masked


def test_mask_url_secrets_noop_without_query():
    url = "https://api.example.com/v1/x"
    assert mask_url_secrets(url) == url


def test_scrub_mapping_masks_url_values():
    payload = {
        "target": "https://api.example.com/v1/x?access_token=s3cret&page=1",
    }
    scrubbed = scrub_mapping(payload)
    assert "s3cret" not in scrubbed["target"]
    assert "page=1" in scrubbed["target"]


def test_compute_hash_deterministic():
    args = {
        "record_id": "abc",
        "at_iso": "2026-04-12T00:00:00+00:00",
        "actor": "u",
        "action": "fs.delete",
        "target": "/x",
        "status": "success",
        "hash_prev": None,
    }
    assert compute_hash(**args) == compute_hash(**args)
