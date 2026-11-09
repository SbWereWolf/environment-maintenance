"""Independent consumer meaning oracle, evaluated before safe command replacement."""
from run_stop_support import fixture


def assert_command_meanings(consumer, rows):
    expected = fixture("consumer-command-meanings.json")[consumer]
    assert [row["id"] for row in rows] == list(expected), consumer + ": application IDs/order"
    for row in rows:
        label = consumer + "/" + row["id"]
        meaning = expected[row["id"]]
        assert row["commands"], label + ": missing launch command"
        launch = row["commands"][-1]
        argv = launch["argv"]
        tail = meaning["argv_tail"]
        # Keep session/terminal launcher choice free. The actual selected
        # executable, action, target and addressing arguments must survive it.
        assert argv[-len(tail):] == tail, label + ": wrong executable/action/target arguments"
        assert launch["cwd"] == meaning["cwd"], label + ": wrong working directory"
        for key, value in meaning["env"].items():
            assert launch["env"].get(key) == value, label + ": wrong environment " + key
        for option, value in meaning["options"].items():
            positions = [i for i, token in enumerate(argv) if token == option]
            assert len(positions) == 1, label + ": missing/repeated " + option
            index = positions[0]
            assert index + 1 < len(argv) and argv[index + 1] == value, label + ": wrong " + option
