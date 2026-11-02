import unittest

from birdbrain import AgentState, Mode


class AgentStateTests(unittest.TestCase):
    def test_state_is_dashboard_serializable(self) -> None:
        state = AgentState(
            mode=Mode.EXPLORING,
            goal="map the play area",
            confidence=0.75,
            observations={"visible_objects": ["blue block"]},
        )

        self.assertEqual(
            state.to_dict(),
            {
                "mode": Mode.EXPLORING,
                "goal": "map the play area",
                "subgoal": None,
                "attention": None,
                "confidence": 0.75,
                "observations": {"visible_objects": ["blue block"]},
            },
        )

    def test_confidence_must_be_normalized(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence"):
            AgentState(confidence=1.1)


if __name__ == "__main__":
    unittest.main()
