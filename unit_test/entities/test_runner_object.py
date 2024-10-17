"""Test script for runner object."""

import unittest

from pywandahydra.entities.runner_object import RunnerObject


class MyTest(unittest.TestCase):
    """Class for testing of the running object."""

    def test_runner_object(self) -> None:
        """Function to test the runner object."""
        try:
            RunnerObject(model="Sewage_transient_WPS.wdi", dir_name="unit_test\\simulation\\")
        except Exception as e:
            self.fail(f"pywandahydra.runner_object() raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
