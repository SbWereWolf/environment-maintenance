'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const packageRoot = path.resolve(__dirname, '..');
const python = path.join(packageRoot, '.venv', 'bin', 'python');

function runProcess(label, executable, args, options = {}) {
  const result = spawnSync(executable, args, { ...options, stdio: 'inherit' });
  if (result.error) {
    console.error(`environment-maintenance: ${label}: ${result.error.message}`);
    return 2;
  }
  if (result.signal) {
    if (result.signal !== 'SIGKILL') {
      // Restore the default action of catchable signals before passing them on.
      const listener = () => {};
      process.on(result.signal, listener);
      process.removeListener(result.signal, listener);
    }
    process.kill(process.pid, result.signal);
    return 2;
  }
  return result.status;
}

module.exports = { packageRoot, python, runProcess };
