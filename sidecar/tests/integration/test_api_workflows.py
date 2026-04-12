"""POST/GET/DELETE /workflows + /workflows/validate."""

from __future__ import annotations

WORKFLOW_YAML = """version: 1
name: example
nodes:
  - id: a
    role: worker
    position: { x: 0, y: 0 }
edges: []
entrypoint: a
"""


def test_create_and_get_workflow(app):
    resp = app.post("/workflows", json={"yaml": WORKFLOW_YAML})
    assert resp.status_code == 200
    workflow = resp.json()
    wf_id = workflow["id"]
    assert workflow["name"] == "example"

    got = app.get(f"/workflows/{wf_id}")
    assert got.status_code == 200
    assert got.json()["yaml"] == WORKFLOW_YAML


def test_validate_workflow_yaml(app):
    resp = app.post("/workflows/validate", json={"yaml": WORKFLOW_YAML})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_validate_invalid_yaml_returns_400(app):
    resp = app.post("/workflows/validate", json={"yaml": "garbage:: ["})
    assert resp.status_code == 400


def test_list_and_delete_workflow(app):
    app.post("/workflows", json={"yaml": WORKFLOW_YAML})
    listed = app.get("/workflows")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
    wf_id = listed.json()[0]["id"]
    deleted = app.delete(f"/workflows/{wf_id}")
    assert deleted.status_code == 200


def test_get_unknown_workflow_returns_404(app):
    resp = app.get("/workflows/does-not-exist")
    assert resp.status_code == 404
