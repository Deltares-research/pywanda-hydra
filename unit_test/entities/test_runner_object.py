from pywandahydra.entities.runner_object import RunnerObject

example = RunnerObject(
    "Sewage_transient_WPS.wdi",
    "unit_test\\simulation\\",
    "c:\\Program Files (x86)\\Deltares\\Wanda 4.6\\Bin\\",
)

results = example.run_model()

print(results)
