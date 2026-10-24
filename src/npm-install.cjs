'use strict';

const path = require('node:path');
const { packageRoot, python, runProcess } = require('./npm-runtime.cjs');

function main() {
  const selected = process.env.ENVIRONMENT_MAINTENANCE_PYTHON;
  if (!selected) {
    console.error('environment-maintenance: ENVIRONMENT_MAINTENANCE_PYTHON is required for installation');
    return 2;
  }
  const created = runProcess('venv', selected,
    ['-P', '-s', '-B', '-m', 'venv', '--copies', path.join(packageRoot, '.venv')],
    { cwd: packageRoot });
  if (created !== 0) {
    return created;
  }
  return runProcess('pip', python,
    ['-P', '-s', '-B', '-m', 'pip', 'install', packageRoot], { cwd: packageRoot });
}

process.exitCode = main();
