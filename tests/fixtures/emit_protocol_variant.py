import json
import os
import sys

action = sys.argv[1]
variant = sys.argv[2]
base = {
    "schema": "environment-maintenance/action-result/v2",
    "requirement_id": "sample",
    "action": action,
}
if action == "check":
    base["state"] = "satisfied"
else:
    base["outcome"] = "completed"

if variant == "empty":
    pass
elif variant == "malformed":
    print("{")
elif variant.startswith("missing-"):
    base.pop(variant.removeprefix("missing-"))
    print(json.dumps(base))
elif variant == "wrong-schema":
    base["schema"] = "wrong/schema"
    print(json.dumps(base))
elif variant == "wrong-schema-type":
    base["schema"] = 1
    print(json.dumps(base))
elif variant == "wrong-id":
    base["requirement_id"] = "other"
    print(json.dumps(base))
elif variant == "wrong-id-type":
    base["requirement_id"] = 1
    print(json.dumps(base))
elif variant == "wrong-action":
    base["action"] = "repair" if action != "repair" else "install"
    print(json.dumps(base))
elif variant == "wrong-action-type":
    base["action"] = 1
    print(json.dumps(base))
elif variant == "forbidden-recognized-field":
    if action == "check":
        base["outcome"] = "completed"
    else:
        base["state"] = "satisfied"
    print(json.dumps(base))
elif variant == "forbidden-advice-field":
    base["cause"] = "not applicable"
    base["recommendations"] = ["not applicable"]
    print(json.dumps(base))
elif variant == "invalid-utf8":
    os.write(1, b"\xff\xfe")
elif variant == "multiple":
    print(json.dumps(base) + "\n" + json.dumps(base))
elif variant.startswith("top-level-"):
    print({
        "top-level-null": "null",
        "top-level-list": "[]",
        "top-level-string": '"value"',
        "top-level-number": "1",
        "top-level-boolean": "true",
    }[variant])
elif variant == "duplicate-key":
    encoded = json.dumps(base, separators=(",", ":"))
    duplicate = '"schema":"environment-maintenance/action-result/v2",'
    print("{" + duplicate + encoded[1:])
elif variant == "unknown-field":
    base["unknown"] = True
    print(json.dumps(base))
elif variant == "wrong-state-type":
    base["state"] = 1
    print(json.dumps(base))
elif variant == "unsupported-state":
    base["state"] = "unknown"
    print(json.dumps(base))
elif variant == "wrong-outcome-type":
    base["outcome"] = 1
    print(json.dumps(base))
elif variant == "unsupported-outcome":
    base["outcome"] = "skipped"
    print(json.dumps(base))
elif variant.startswith("unavailable-"):
    base["state"] = "unavailable"
    base["cause"] = "offline"
    base["recommendations"] = ["Connect mirror."]
    field = variant.removeprefix("unavailable-")
    if field == "empty-cause":
        base["cause"] = ""
    elif field == "blank-cause":
        base["cause"] = "   "
    elif field == "wrong-cause":
        base["cause"] = []
    elif field == "empty-recommendations":
        base["recommendations"] = []
    elif field == "wrong-recommendations":
        base["recommendations"] = "connect"
    elif field == "empty-recommendation":
        base["recommendations"] = [""]
    elif field == "blank-recommendation":
        base["recommendations"] = ["   "]
    elif field == "wrong-recommendation-item":
        base["recommendations"] = [1]
    elif field == "forbidden-outcome":
        base["outcome"] = "completed"
    elif field == "missing-cause":
        base.pop("cause")
    elif field == "missing-recommendations":
        base.pop("recommendations")
    print(json.dumps(base))
else:
    raise SystemExit("unknown variant")
