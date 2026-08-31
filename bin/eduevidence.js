#!/usr/bin/env node
/**
 * EduEvidence npm CLI — wraps install.sh from the published package root.
 *
 *   npm install -g eduevidence
 *   eduevidence skill              # interactive host picker (default)
 *   eduevidence skill --host claude
 *   npx eduevidence skill --list-hosts
 */
'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PKG_ROOT = path.resolve(__dirname, '..');
const INSTALL_SH = path.join(PKG_ROOT, 'install.sh');

function usage() {
  console.log(`eduevidence ${readPkgVersion()} — Evidence-Based Education Decision Skill

Install (Python runtime + self-check):
  eduevidence install [--dev] [--dry-run]

Install as AI Agent Skill:
  eduevidence skill                         Interactive host picker
  eduevidence skill --host <name>           claude | codex | cursor | all | …
  eduevidence skill --dest <dir>            Custom skill root (creates <dir>/eduevidence/)
  eduevidence skill --list-hosts            Supported agents and install paths
  eduevidence skill --dry-run               Preview without writing

Legacy install.sh flags (also accepted):
  eduevidence --skill [--host claude] [--dry-run]
  eduevidence --list-hosts

Requires: bash, Python 3.10+ (for install / scripts)
Docs: https://github.com/37chengshan/eduevidence/blob/main/docs/install-guide.md
`);
}

function readPkgVersion() {
  try {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8'),
    );
    return pkg.version || '';
  } catch {
    return '';
  }
}

function runInstallSh(args) {
  if (!fs.existsSync(INSTALL_SH)) {
    console.error('ERROR: install.sh not found in package:', PKG_ROOT);
    process.exit(1);
  }
  if (!fs.existsSync(path.join(PKG_ROOT, 'SKILL.md'))) {
    console.error('ERROR: SKILL.md not found in package:', PKG_ROOT);
    process.exit(1);
  }

  const result = spawnSync('bash', [INSTALL_SH, ...args], {
    cwd: PKG_ROOT,
    stdio: 'inherit',
    env: process.env,
  });
  if (result.error) {
    console.error('ERROR: failed to run install.sh:', result.error.message);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

function mapArgs(argv) {
  if (argv.length === 0) {
    usage();
    return null;
  }

  const first = argv[0];
  if (first === '-h' || first === '--help' || first === 'help') {
    usage();
    return null;
  }

  if (first === 'install') {
    return argv.slice(1);
  }

  if (first === 'skill') {
    const rest = argv.slice(1);
    if (rest.includes('--list-hosts')) {
      return ['--list-hosts'];
    }
    const out = ['--skill', '--skill-only'];
    for (let i = 0; i < rest.length; i += 1) {
      const arg = rest[i];
      if (arg === '--host' || arg === '--dest') {
        out.push(arg, rest[i + 1] ?? '');
        i += 1;
        continue;
      }
      if (arg === '--dry-run') {
        out.push('--dry-run');
        continue;
      }
      console.error(`ERROR: unknown skill flag: ${arg}`);
      usage();
      process.exit(1);
    }
    return out;
  }

  // Pass through legacy install.sh flags (--skill, --dev, --list-hosts, …).
  return argv;
}

function main() {
  const argv = process.argv.slice(2);
  const mapped = mapArgs(argv);
  if (mapped === null) {
    process.exit(0);
  }
  runInstallSh(mapped);
}

main();
