"""Debug scenarios from Excel files."""

from pathlib import Path

if __name__ == "__main__":
    print(f"Debugging scenarios from Excel files in {Path(__file__).parent}")
    from pywandahydra.scenarios.mapper import ScenarioLoadOptions, load_scenarios

    data_path = Path(r"c:\repositories\pywanda-hydra\test_data\scenarios\ExampleParameter.xls")

    options = ScenarioLoadOptions()

    # Load scenarios
    scenarios = load_scenarios(data_path, options=options)
