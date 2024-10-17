"""Module containging the RunnerObject class.

This class is used for running the different scenarios
and creating their output."""

from pathlib import Path

import pywanda

from pywandahydra.entities.parameter import input_object, output_object


class RunnerObject:
    """Class used for running the different scenarios
    and creating their output."""

    def __init__(
        self,
        model: str,
        dir_name: str,
        wanda_bin: str = "c:\\Program Files (x86)\\Deltares\\Wanda 4.6\\Bin\\",
    ):
        # Set a path for the wanda model
        self.model_name = model
        self.model_path = dir_name
        self.bin = wanda_bin
        # self.model: WandaModel

    def set_inputs(input: list[input_object]) -> None:  # type: ignore
        pass

    def get_output(output: list[output_object]) -> list[output_object]:  # type: ignore
        pass

    def run_model(self) -> None:
        """Function to run the model
        Open de model, run both steady and unsteady

        Returns:
        --------
        result: list of strings"""
        # Open the model

        model = pywanda.WandaModel(str(Path(self.model_path, self.model_name)), self.bin)
        # Store all the input information
        print("Save model input")
        try:
            model.save_model_input
        except MemoryError as e:
            print(e)
        # Run the steady state
        print("Run steady model")
        try:
            model.run_steady()
        except RuntimeError as e:
            print(e)
        # Run the unsteady state
        if model.get_property("Simulation time").get_scalar_float() > 0:
            print("Run unsteady model")
            try:
                model.run_unsteady()
            except RuntimeError as e:
                print(e)
        return None
