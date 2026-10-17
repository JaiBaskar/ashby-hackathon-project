import type { NextConfig } from 'next'
import { readAppSettings, settingsEnv } from './app-settings'

// The browser only talks to Next.js. /api/* is forwarded to the FastAPI service, which runs all the
// Python ML code (ingest, tiling, CONCH, ranking). API_URL is read when `next dev` or `next build` starts.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

// Next buffers proxied request bodies and cuts them off at 10 MB by default, which breaks slide uploads.
// Allow config.yaml's max_upload_mb plus room for the multipart wrapper, so FastAPI can answer 413 itself.
const { maxUploadMb } = readAppSettings(process.cwd())

const nextConfig: NextConfig = {
  // max_upload_mb and default_mpp, for the upload screen (process.env.MAX_UPLOAD_MB, process.env.DEFAULT_MPP).
  env: settingsEnv(process.cwd()),
  experimental: { proxyClientMaxBodySize: `${maxUploadMb + 1}mb` },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiUrl}/api/:path*` }]
  },
}

export default nextConfig
