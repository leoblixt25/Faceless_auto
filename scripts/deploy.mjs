// Robust deploy: build the SPA, deploy the worker, then re-apply all
// secrets. Cloudflare Workers wipes secrets on every `wrangler deploy`, so
// re-applying them here is what keeps /api/generate and /api/video working
// after a deploy (otherwise submit + delete silently fail).
import { execFileSync, spawnSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const workerDir = resolve(root, 'worker')

function run(cmd, args, opts = {}) {
  console.log(`\n> ${cmd} ${args.join(' ')}`)
  const res = spawnSync(cmd, args, { stdio: 'inherit', shell: true, cwd: opts.cwd || root, ...opts })
  if (res.status !== 0) {
    throw new Error(`Command failed: ${cmd} ${args.join(' ')} (exit ${res.status})`)
  }
}

// Put a single secret from a value string (fed via stdin so special chars are safe).
function putSecret(name, value) {
  if (!value) {
    console.warn(`! Skipping ${name}: no value provided`)
    return
  }
  execFileSync('npx', ['wrangler', 'secret', 'put', name], {
    input: value,
    cwd: workerDir,
    shell: true,
    stdio: ['pipe', 'inherit', 'inherit'],
  })
}

console.log('==> Building frontend (npm run build)')
run('npm', ['run', 'build'])

console.log('==> Deploying worker (wrangler deploy)')
run('npx', ['wrangler', 'deploy'], { cwd: workerDir })

console.log('\n==> Re-applying worker secrets (wiped by deploy)')

// PATs from .env.secrets (KEY=VALUE, one per line).
const secretsPath = resolve(workerDir, '.env.secrets')
if (existsSync(secretsPath)) {
  const text = readFileSync(secretsPath, 'utf8')
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq === -1) continue
    const key = line.slice(0, eq).trim()
    const value = line.slice(eq + 1).trim()
    putSecret(key, value)
  }
} else {
  console.warn('! worker/.env.secrets not found; skipping PAT secrets')
}

// Firebase service-account JSON (raw file content).
const saPath = resolve(workerDir, '.firebase-credentials.json')
if (existsSync(saPath)) {
  putSecret('FIREBASE_CREDENTIALS', readFileSync(saPath, 'utf8').trim())
} else {
  console.warn('! worker/.firebase-credentials.json not found; skipping FIREBASE_CREDENTIALS')
}

console.log('\n==> Deploy complete. Secrets re-applied.')
