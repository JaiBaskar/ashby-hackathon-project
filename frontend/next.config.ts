import { readFileSync } from 'node:fs'
import path from 'node:path'
import type { NextConfig } from 'next'

// The browser only talks to Next.js. /api/* is forwarded to the FastAPI service, which runs all the
// Python ML code (ingest, tiling, CONCH, ranking). API_URL is read when `next dev` or `next build` starts.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

// Next buffers proxied request bodies and cuts them off at 10 MB by default, which breaks slide uploads.
// Allow config.yaml's max_upload_mb plus room for the multipart wrapper, so FastAPI can answer 413 itself.
const config = readFileSync(path.join(process.cwd(), '..', 'config.yaml'), 'utf8')
const maxUploadMb = Number(/^max_upload_mb:\s*(\d+)/m.exec(config)?.[1])
if (!maxUploadMb) throw new Error('config.yaml needs max_upload_mb')

const nextConfig: NextConfig = {
  experimental: { proxyClientMaxBodySize: `${maxUploadMb + 1}mb` },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiUrl}/api/:path*` }]
  },
}

export default nextConfig
