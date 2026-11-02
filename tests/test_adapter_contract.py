import unittest

from birdbrain.adapters import Action, Observation


class AdapterValueObjectTests(unittest.TestCase):
    def test_action_and_observation_values(self) -> None:
        action = Action("turn", {"radians": 0.5})
        observation = Observation(1.25, {"heading": 0.5})

        self.assertEqual(action.name, "turn")
        self.assertEqual(observation.values["heading"], 0.5)


if __name__ == "__main__":
    unittest.main()
