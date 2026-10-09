# Deploying for free

The site is fully static (`dist/` after `npm run build`). No server, database or secrets.

## Option A: Cloudflare Pages (recommended)

Free tier: unlimited bandwidth, custom domain, a preview URL per branch.

1. Push this repo to GitHub.
2. In the Cloudflare dashboard: **Workers & Pages → Create → Pages → Connect to Git**, pick the repo.
3. Build settings:
   - Framework preset: **Astro**
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Environment variable: `NODE_VERSION` = `22`, and `SITE_URL` = your final URL (for example `https://free-agent-harness.pages.dev`)
4. Save and deploy. Every push to `main` redeploys; every other branch gets a preview URL.
5. Optional: **Custom domains** tab to add your own domain. Optional: **Web Analytics** (cookieless) in the Cloudflare dashboard.

## Option B: GitHub Pages

1. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Actions → Deploy to GitHub Pages → Run workflow**. The workflow sets `BASE_PATH=/<repo-name>` so links work under `https://<user>.github.io/<repo-name>/`.

## Option C: anywhere else

Netlify, Vercel, Render static sites, or any web server: build with `npm run build` and serve `dist/`. Set `BASE_PATH` only if the site lives under a sub-path.

## Notes

- Code labs load Python (Pyodide 0.27.2) from cdn.jsdelivr.net on first Run. To self-host it instead, copy `node_modules/pyodide/{pyodide.js,pyodide.asm.js,pyodide.asm.wasm,python_stdlib.zip,pyodide-lock.json}` into `public/pyodide/` and build with `PUBLIC_PYODIDE_URL=/pyodide/`.
- Search (Pagefind) is generated during `npm run build`, so it only works on a built site, not in `npm run dev`.
