"""Policies routes — list / upsert / simulate."""

from __future__ import annotations


def test_list_policies(app):
    resp = app.get("/policies")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_simulate_policy(app, app_services):
    pid = next(iter(app_services.policies.keys()))
    body = {
        "policy_id": pid,
        "scenarios": [{"tool_id": "fs.delete", "args": {"path": "/tmp/x"}}],
    }
    resp = app.post("/policies/simulate", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_id"] == pid
    assert len(data["results"]) == 1
    # trusted policy -> allow
    assert data["results"][0]["effect"] == "allow"
