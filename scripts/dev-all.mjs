import { spawn } from 'node:child_process'

const rootDir = new URL('..', import.meta.url)
const backendDir = new URL('backend/', rootDir)
const frontendDir = new URL('frontend/', rootDir)

const host = process.env.DEV_HOST || '127.0.0.1'
const backendPort = process.env.BACKEND_PORT || '19000'
const frontendPort = process.env.FRONTEND_PORT || '5173'
const pythonBin = process.env.PYTHON_BIN || 'python3'
const frontendRunner = process.env.FRONTEND_PM || 'pnpm'
const frontendArgs = frontendRunner === 'npm'
  ? ['run', 'dev', '--', '--host', host, '--port', frontendPort]
  : ['dev', '--', '--host', host, '--port', frontendPort]

if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log([
    'Usage: pnpm dev:all',
    '',
    'Starts both development servers:',
    `  Backend:  ${pythonBin} -m uvicorn app.main:app --host ${host} --port ${backendPort} --reload`,
    `  Frontend: ${frontendRunner} ${frontendArgs.join(' ')}`,
    '',
    'Optional environment variables:',
    '  DEV_HOST=127.0.0.1',
    '  BACKEND_PORT=19000',
    '  FRONTEND_PORT=5173',
    '  PYTHON_BIN=python3',
    '  FRONTEND_PM=pnpm',
  ].join('\n'))
  process.exit(0)
}

const children = []
let shuttingDown = false

function start(name, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: 'inherit',
    env: process.env,
  })
  children.push({ name, child })

  child.on('exit', (code, signal) => {
    if (shuttingDown) return
    const reason = signal ? `signal ${signal}` : `code ${code ?? 0}`
    console.log(`[dev:all] ${name} exited with ${reason}; stopping remaining services.`)
    shutdown(code ?? 0)
  })

  child.on('error', error => {
    if (shuttingDown) return
    console.error(`[dev:all] failed to start ${name}: ${error.message}`)
    shutdown(1)
  })
}

function shutdown(exitCode = 0) {
  shuttingDown = true
  for (const { child } of children) {
    if (!child.killed && child.exitCode === null) {
      child.kill('SIGTERM')
    }
  }
  setTimeout(() => process.exit(exitCode), 250)
}

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))

console.log(`[dev:all] Backend  http://${host}:${backendPort}`)
console.log(`[dev:all] Frontend http://${host}:${frontendPort}`)

start(
  'backend',
  pythonBin,
  ['-m', 'uvicorn', 'app.main:app', '--host', host, '--port', backendPort, '--reload'],
  backendDir,
)

start(
  'frontend',
  frontendRunner,
  frontendArgs,
  frontendDir,
)
