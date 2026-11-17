"""The npm source must carry the real command resources of the selected wheel."""
from importlib.resources import files
import os
from pathlib import Path
import tarfile


def test_npm_archive_preserves_installed_command_resources():
    archive = Path(os.environ['ENV2_PACKAGE_ARCHIVE']).resolve(strict=True)
    resources = files('environment_maintenance').joinpath('resources', 'commands')
    expected = {p.name: p.read_bytes() for p in resources.iterdir() if p.name.endswith('.bash')}
    assert {'read.bash', 'write.bash', 'invoke.bash'} <= set(expected)
    with tarfile.open(archive) as package:
        members = set(package.getnames())
        missing = ['package/src/environment_maintenance/resources/commands/' + name
                   for name in expected
                   if 'package/src/environment_maintenance/resources/commands/' + name not in members]
        assert missing == [], missing
        for name, content in expected.items():
            assert package.extractfile('package/src/environment_maintenance/resources/commands/' + name).read() == content
