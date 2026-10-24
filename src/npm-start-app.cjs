#!/usr/bin/env node
'use strict';

const { python, runProcess } = require('./npm-runtime.cjs');

function main() {
  return runProcess('python', python,
    ['-P', '-s', '-B', '-m', 'environment_maintenance', ...process.argv.slice(2)]);
}

process.exitCode = main();
