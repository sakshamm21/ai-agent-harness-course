# Hosting (optional)

The course is meant to be cloned and run locally (see the README). Nothing here is needed for that. These notes
are for later, if you decide to put a public copy online.

The site is fully static (`dist/` after `npm run build`): no server, no database, no secrets. Progress lives in
each learner's browser; `/progress/` exports it to a file and imports it on another device.

## Vercel

Free Hobby plan, a stable `https://<project>.vercel.app` link, HTTPS, a production redeploy on every push to
`main`, and a preview link for every other branch and pull request. Vercel detects Astro; the build command is
`npm run build` and the output directory `dist`.

1. Go to <https://vercel.com/new> and import this repository under Import Git Repository (grant the Vercel
   GitHub app access to it if it isn't listed).
2. Set the project name to `free-agent-harness` (that becomes the link) and press **Deploy**. No environment
   variables are needed.
3. Done. Every push to `main` updates the site.

`SITE_URL` and the GitHub links on the site come from Vercel's build environment automatically. Set `SITE_URL`
only if you add a custom domain (**Settings → Domains**).

**Renaming the repo** needs nothing: Vercel follows the repo by its ID, GitHub redirects old links, and the
site's GitHub links are rebuilt from the new name on the next push. If the Vercel project ever shows the repo
as disconnected, reconnect it under **Settings → Git**.

**Adding another course** to this repo needs nothing either; it deploys with the rest. A course in its own repo
is one more Vercel project, imported the same way.

## Cloudflare Pages

Unlimited bandwidth and no non-commercial clause, at the cost of creating a Cloudflare account.
Workers & Pages → Create → Pages → Connect to Git, pick the repo. Build command `npm run build`, output
`dist`, environment variables `NODE_VERSION=22` and `SITE_URL=https://<project>.pages.dev`. Every push to `main`
redeploys.

## GitHub Pages (fallback)

Repo **Settings → Pages → Source: GitHub Actions**, then **Actions → Deploy to GitHub Pages → Run workflow**.
The site lives under `https://<user>.github.io/<repo-name>/`, so renaming the repo changes the link; the
workflow sets `BASE_PATH` to match.

## Notes

- Pyodide (about 14 MB) is copied into `public/pyodide/` by `npm install` and ships with the build, so a hosted copy serves its own Python. jsDelivr is only a fallback if those files are missing.
- Search (Pagefind) is generated during `npm run build`, so it only works on a built site, not in `npm run dev`.
