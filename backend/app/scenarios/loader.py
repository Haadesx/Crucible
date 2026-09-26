from app.models.scenario import Scenario
from app.scenarios.seeds import seed_scenarios


class ScenarioCatalog:
    def __init__(self) -> None:
        self._scenarios = {scenario.id: scenario for scenario in seed_scenarios()}

    def all(self) -> list[Scenario]:
        return list(self._scenarios.values())

    def by_carrier(self, carrier: str) -> Scenario:
        for scenario in self._scenarios.values():
            if scenario.content_source == carrier:
                return scenario
        raise KeyError(f"no scenario supports carrier {carrier}")

    def get(self, scenario_id: str) -> Scenario:
        return self._scenarios[scenario_id]
