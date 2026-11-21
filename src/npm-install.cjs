'use strict';

const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { packageRoot, python, runProcess } = require('./npm-runtime.cjs');

function verifiedWheels(directory) {
  const manifest = fs.readFileSync(path.join(directory, 'SHA256SUMS'), 'utf8');
  const wheels = new Map();
  for (const line of manifest.trimEnd().split('\n')) {
    const entry = /^([0-9a-f]{64})  ([\w.-]+\.whl)$/.exec(line);
    if (!entry || wheels.has(entry[2])) {
      throw new Error('invalid wheel inventory: ' + directory);
    }
    const [, digest, name] = entry;
    const wheel = path.join(directory, name);
    if (createHash('sha256').update(fs.readFileSync(wheel)).digest('hex') !== digest) {
      throw new Error('wheel SHA-256 mismatch: ' + wheel);
    }
    wheels.set(name, wheel);
  }
  const found = fs.readdirSync(directory).filter(name => name.endsWith('.whl'));
  if (found.length !== wheels.size || found.some(name => !wheels.has(name))) {
    throw new Error('wheel inventory differs: ' + directory);
  }
  return wheels;
}

function main() {
  const selected = process.env.ENVIRONMENT_MAINTENANCE_PYTHON;
  if (!selected) {
    console.error('environment-maintenance: ENVIRONMENT_MAINTENANCE_PYTHON is required for installation');
    return 2;
  }
  const em = require('../package.json');
  const cePath = require.resolve('command-execution/package.json');
  const ce = require(cePath);
  if (ce.name !== 'command-execution' || ce.version !== em.dependencies['command-execution']) {
    throw new Error('installed command-execution version differs from the declared npm dependency');
  }

  const own = verifiedWheels(path.join(packageRoot, 'vendor'));
  const emWheel = own.get(`environment_maintenance-${em.version}-py3-none-any.whl`);
  const dependencies = verifiedWheels(path.join(path.dirname(cePath), 'vendor'));
  const ceWheel = `command_execution-${ce.version}-py3-none-any.whl`;
  if (!emWheel || own.size !== 1 || !dependencies.has(ceWheel)) {
    throw new Error('required EM or CE wheel missing from distribution');
  }

  const cwd = packageRoot;
  const runtime = path.dirname(path.dirname(python));
  // Create a clean runtime on every successful lifecycle, including reinstallation.
  const created = runProcess('venv', selected,
    ['-I', '-B', '-m', 'venv', '--clear', '--copies', runtime], { cwd });
  if (created !== 0) {
    return created;
  }
  const env = { ...process.env, PIP_CONFIG_FILE: '/dev/null' };
  const pip = ['-I', '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check', '--no-cache-dir'];
  const installed = runProcess('pip', python, [...pip, 'install', '--no-index', '--no-deps',
    emWheel, ...dependencies.values()], { cwd, env });
  if (installed !== 0) {
    return installed;
  }
  const checked = runProcess('pip check', python, [...pip, 'check'], { cwd, env });
  if (checked !== 0) {
    return checked;
  }
  return runProcess('installed versions', python, ['-I', '-B', '-c', [
    'from importlib.metadata import version',
    'import sys',
    'assert version("environment-maintenance") == sys.argv[1]',
    'assert version("command-execution") == sys.argv[2]',
  ].join('\n'), em.version, ce.version], { cwd, env });
}

try {
  process.exitCode = main();
} catch (error) {
  console.error('environment-maintenance: ' + error.message);
  process.exitCode = 2;
}
