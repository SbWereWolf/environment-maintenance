"""Test-owned declarations and literal expectations; no product imports."""
import json
from run_stop_support import ROOT, application, write


RESOURCE_FIXTURES = ROOT / "tests/fixtures/application-resources"


def resource_fixture(name):
    return json.loads((RESOURCE_FIXTURES / name).read_text(encoding="utf-8"))


def expected_list(lab, variant="a"):
    # Replace one arrangement path, not resource expressions or observed output.
    raw = (RESOURCE_FIXTURES / f"expected-{variant}.json").read_text(encoding="utf-8")
    return json.loads(raw.replace("${test_root}", str(lab.root)))


def set_values(lab, variant="a", *, path=None):
    values = json.loads(lab.values.read_text())
    data = resource_fixture(f"values-{variant}.json")
    directory = data.pop("queue_directory")
    values.update(data, queue_root=str(lab.root / directory))
    write(path or lab.values, values)


def arrange_resources(lab):
    set_values(lab)
    rows = []
    for name, resources in resource_fixture("declarations.json").items():
        row = application(name)
        row["resources"] = resources
        rows.append(row)
    rows.append(application("plain"))
    lab.run_rows(rows)


def expected_started(lab, names, variant="a"):
    rows = expected_list(lab, variant)["applications"]
    answer = {}
    for name in names:
        row = rows[name]
        row["pgid"] = lab.started(name)["pgid"]
        answer[name] = row
    return answer


def unchanged_inputs(lab):
    return {path: path.read_bytes() for path in (lab.main, lab.values, lab.root / "run.json")}


def assert_read_only(lab, before):
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert lab.labels() == []
    assert not lab.store.exists()


def environment_record(answer, title):
    assert answer["operation"] == "stop-list" and answer["status"] == "succeeded"
    assert answer["errors"] == []
    matches = [row for row in answer["environments"] if row["environment"] == title]
    assert len(matches) == 1
    return matches[0]


def stored_applications(lab, title):
    # Observe the wire file independently of the production registry reader.
    path = lab.state_path(title)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["environment-title"] == title
    return document["applications"]


def persisted_resources(lab, title):
    # A fresh CLI must reconstruct the snapshot; the storage layout is its owner’s choice.
    answer = environment_record(lab.answer("stop", "list", "--env", title), title)
    raw = stored_applications(lab, title)
    assert set(raw) == set(answer["applications"])
    for name, row in answer["applications"].items():
        assert raw[name]["pgid"] == row["pgid"]
    return answer["applications"]
