import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_arena_lifecycle() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        start = client.post(
            "/arena/start",
            json={"generations": 2, "red_population": 4, "blue_population": 4, "matchups_per_genome": 2},
        )
        assert start.status_code == 200
        run_id = start.json()["run_id"]
        for _ in range(100):
            status = client.get("/arena/status").json()
            if status["status"] in {"completed", "error"}:
                break
            time.sleep(0.01)
        assert status["status"] == "completed"
        generations = client.get(f"/generations?run_id={run_id}").json()
        assert len(generations) == 2
        assert generations[0]["total_battles"] == 8


def test_replay_and_websocket_are_available() -> None:
    with TestClient(create_app()) as client:
        client.post(
            "/arena/start",
            json={"generations": 2, "red_population": 4, "blue_population": 4, "matchups_per_genome": 2},
        )
        for _ in range(100):
            if client.get("/arena/status").json()["status"] == "completed":
                break
            time.sleep(0.01)
        lineage = client.get("/arena/lineage").json()
        attack = lineage["red"][0]["genome"]["id"]
        defense = lineage["blue"][0]["genome"]["id"]
        replay = client.post(
            "/replay",
            json={"attack_id": attack, "defense_id": defense, "scenario_id": "DOC-001"},
        )
        assert replay.status_code == 200
        assert "gateway_decisions" in replay.json()
        with client.websocket_connect("/ws/arena") as websocket:
            assert websocket.receive_json()["type"]


def test_harness_replay_compares_naked_and_protected_versions() -> None:
    with TestClient(create_app()) as client:
        start = client.post(
            "/arena/start",
            json={"generations": 2, "red_population": 4, "blue_population": 6, "matchups_per_genome": 2},
        )
        run_id = start.json()["run_id"]
        for _ in range(200):
            if client.get("/arena/status").json()["status"] == "completed":
                break
            time.sleep(0.01)
        assert client.get("/arena/status").json()["status"] == "completed"

        lineage = client.get(f"/arena/lineage?run_id={run_id}").json()
        attack_id = lineage["red"][0]["genome"]["id"]
        harnesses = client.get(f"/harnesses?run_id={run_id}").json()
        protected_id = next(
            item["version"]["id"]
            for item in harnesses
            if item["version"]["tool_policy"]["goal_binding_enabled"]
        )
        response = client.post(
            "/replay/compare",
            json={
                "attack_id": attack_id,
                "scenario_id": "DOC-001",
                "harness_b_id": protected_id,
            },
        )

        assert response.status_code == 200
        comparison = response.json()
        assert comparison["same_attack"] is True
        assert comparison["different_outcome"] is True
        assert comparison["harness_a"]["episode"]["attack_success"] is True
        assert comparison["harness_b"]["episode"]["attack_success"] is False
        assert comparison["harness_a"]["harness"]["id"] == "HARNESS-NAKED"
        assert comparison["harness_b"]["harness"]["id"] == protected_id
        assert comparison["harness_a"]["episode"]["harness_graph"]["nodes"] == [
            {"id": "input", "label": "INPUT", "kind": "input", "enabled": True, "config": {}},
            {"id": "agent", "label": "TARGET AGENT", "kind": "agent", "enabled": True, "config": {"model": "unchanged"}},
            {"id": "tool", "label": "SANDBOX TOOL", "kind": "tool", "enabled": True, "config": {}},
        ]
        assert any(
            step["stage"] == "Goal binder"
            for step in comparison["harness_b"]["episode"]["runtime_trace"]
        )
