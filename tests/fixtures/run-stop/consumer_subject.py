"""Invoke existing consumer components against test-owned output, never a harness session."""
import importlib
import json
from pathlib import Path
import re
import runpy
import sys
from types import SimpleNamespace

mode, descriptor_path, name, output_path = sys.argv[1:5]
descriptor = json.loads(Path(descriptor_path).read_text())[name]
output = Path(output_path)
if mode == "imports":
    importlib.import_module("poise_environment.profile")
    if descriptor["kind"] == "documents":
        runpy.run_path(descriptor["publisher"])
    if descriptor.get("handler"):
        runpy.run_path(descriptor["handler"])
    print("Consumer components imported")
elif mode == "publish":
    if descriptor["kind"] == "profile":
        from poise_environment.profile import generate
        arguments = SimpleNamespace(
            source=descriptor["source"], output=str(output),
            state=str(output.parent / "state"), repository=descriptor["repository"],
            project=name, base_ref="main", author_name="Fixture Author",
            author_email="fixture@example.invalid", template="common",
            module_path=descriptor["module_path"], profile_spec=descriptor["spec"])
        print(json.dumps(generate(arguments)))
    else:
        subject = runpy.run_path(descriptor["publisher"])
        specification = json.loads(Path(descriptor["spec"]).read_text())
        # Only projection parameters are substituted. Runtime command parameters
        # stay in the published document for the real EM renderer.
        names = set(re.findall(r"\$\{([^}]+)\}", json.dumps(specification)))
        values = {key: str(output.parent / ("fixture-" + key)) for key in names}
        values.update(source_root=descriptor["poise_source"], repository=descriptor["repository"],
                      profile_root=str(output), task_root=str(output.parent),
                      module_path=descriptor["module_path"], path="/usr/bin:/bin",
                      node="/usr/bin/node", npm_entry_point="/usr/bin/npm",
                      bootstrap_python=sys.executable, python=sys.executable)
        subject["publish_documents"](specification, descriptor["source"], output, values)
        print(json.dumps({"status": "published", "profile": str(output)}))
elif mode == "forward":
    subject = runpy.run_path(descriptor["handler"])
    raise SystemExit(subject["execute"](sys.argv[5:]))
elif mode == "interpret":
    main = json.loads((output / descriptor["main"]).read_text())
    run = json.loads((output / main["operations"]["run"]).read_text())
    for row in run["applications"]:
        chosen = row["commands"][-1]["interpreter"]
        binding = main["interpreters"][chosen["name"]]
        interpreter = getattr(importlib.import_module(binding["module"]), binding["attribute"])
        raw = {"exit_code": 0, "stdout": b'{"status":"submitted","pgid":87654321}',
               "stderr": b""}
        result = interpreter.interpret(raw, chosen["options"])
        assert result["success"] is True, (row["id"], result)
    print("Declared final interpreters accept submitted groups")
else:
    raise ValueError(mode)
