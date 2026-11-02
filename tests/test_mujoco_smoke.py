"""Minimal headless proof that the bundled MuJoCo engine runs."""

import unittest

import mujoco

FALLING_BODY_XML = """
<mujoco model="birdbrain_smoke_test">
  <option timestep="0.01" gravity="0 0 -9.81"/>
  <worldbody>
    <geom name="floor" type="plane" size="1 1 0.1"/>
    <body name="test_body" pos="0 0 1">
      <freejoint/>
      <geom type="sphere" size="0.05" mass="0.1"/>
    </body>
  </worldbody>
</mujoco>
"""


class MuJoCoSmokeTests(unittest.TestCase):
    def test_headless_simulation_advances_and_applies_gravity(self) -> None:
        model = mujoco.MjModel.from_xml_string(FALLING_BODY_XML)
        data = mujoco.MjData(model)
        initial_height = float(data.qpos[2])

        for _ in range(10):
            mujoco.mj_step(model, data)

        self.assertAlmostEqual(data.time, 0.1)
        self.assertLess(float(data.qpos[2]), initial_height)


if __name__ == "__main__":
    unittest.main()
