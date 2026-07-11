#!/usr/bin/env node
/**
 * run-verification.mjs — new_stock 的本機驗證入口（供 ai-coding-relay auto-round 每輪呼叫）。
 *
 * 契約（relay scripts/auto-round.mjs parseVerificationJson）：
 *   stdout 輸出一個 JSON 物件，含 `ok`（boolean）與 `commands`（各指令結果）。
 *   ok=false 時 exit 1，但仍輸出合法 JSON。
 *
 * 驗證內容：
 *   1. backend pytest（排除 2 個「本機資料新鮮度」相依的 doctor 測試——它們隨市場資料
 *      是否過期而翻轉，與程式碼正確性無關；資料回補後可移除 deselect）
 *   2. frontend tsc --noEmit
 *
 * 前置：backend/.venv 需存在（python3.12 -m venv backend/.venv && pip install -r requirements.txt && pip install requests）。
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const PY = join(ROOT, 'backend', '.venv', 'bin', 'python');
const TSC = join(ROOT, 'frontend', 'node_modules', '.bin', 'tsc');
const PER_COMMAND_TIMEOUT_MS = 15 * 60 * 1000;

// 本機資料時效相依（block vs warn 隨資料過期天數翻轉），非程式碼正確性；見檔頭說明。
const DOCTOR_DATA_DEPENDENT_DESELECTS = [
  '--deselect', 'tests/test_doctor.py::test_doctor_warns_for_fundamentals_and_unrecorded_actionable_items',
  '--deselect', 'tests/test_doctor.py::test_doctor_json_cli_outputs_machine_readable_report',
];

function run(name, command, args, cwd) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    let out = '';
    let child;
    try {
      child = spawn(command, args, { cwd, env: process.env });
    } catch (err) {
      resolve({ name, command: `${command} ${args.join(' ')}`, exitCode: null, ok: false, durationMs: 0, tail: String(err?.message ?? err) });
      return;
    }
    const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch { /* ignore */ } }, PER_COMMAND_TIMEOUT_MS);
    child.stdout.on('data', (c) => { out += c.toString(); });
    child.stderr.on('data', (c) => { out += c.toString(); });
    child.on('error', (err) => { clearTimeout(timer); resolve({ name, command: `${command} ${args.join(' ')}`, exitCode: null, ok: false, durationMs: Date.now() - startedAt, tail: err.message }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ name, command: `${command} ${args.join(' ')}`, exitCode: code, ok: code === 0, durationMs: Date.now() - startedAt, tail: out.split('\n').slice(-8).join('\n').slice(-1200) });
    });
  });
}

const startedAt = new Date().toISOString();
const commands = [];

if (!existsSync(PY)) {
  commands.push({ name: 'backend-pytest', command: PY, exitCode: null, ok: false, durationMs: 0, tail: 'backend/.venv 不存在。請先：python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt requests' });
} else {
  commands.push(await run('backend-pytest', PY, ['-m', 'pytest', 'tests/', '-q', ...DOCTOR_DATA_DEPENDENT_DESELECTS], join(ROOT, 'backend')));
}

if (!existsSync(TSC)) {
  commands.push({ name: 'frontend-tsc', command: TSC, exitCode: null, ok: false, durationMs: 0, tail: 'frontend/node_modules 不存在。請先：cd frontend && npm install' });
} else {
  commands.push(await run('frontend-tsc', TSC, ['--noEmit'], join(ROOT, 'frontend')));
}

const ok = commands.every((c) => c.ok);
process.stdout.write(`${JSON.stringify({ ok, startedAt, finishedAt: new Date().toISOString(), commands }, null, 2)}\n`);
process.exitCode = ok ? 0 : 1;
