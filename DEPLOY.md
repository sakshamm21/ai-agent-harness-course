# Public copy on Vercel

Learners take the course by cloning the repo and running it locally (see the README). The Vercel copy is an
always-on public showcase you can send to anyone. It is fully static: no sign-in, no database, no secrets.
Each visitor's progress is saved in their own browser, and **Your progress** in the footer lets them move it
with a file.

## Set it up (once)

1. Go to <https://vercel.com/new> and, under **Import Git Repository**, pick this repo. If it isn't listed,
   choose **Adjust GitHub App Permissions** and give Vercel access to it.
2. Set the project name to `free-agent-harness` (that becomes `https://free-agent-harness.vercel.app`, or a
   close variant if the name is taken). Leave every other setting as is; `vercel.json` holds them.
3. Press **Deploy**.

From then on every push to `main` redeploys the public site, and every other branch or pull request gets its
own preview link. The free Hobby plan covers this (it is meant for personal, non-commercial projects).

## Good to know

- **Renaming the repo** needs nothing: Vercel follows the repo by its ID, GitHub redirects old links, and the
  site's GitHub links are rebuilt from the new name on the next deploy. If the project ever shows the repo as
  disconnected, reconnect it under **Settings → Git**.
- **Adding courses** to this repo needs nothing; they deploy with the rest. A course in another repo is one
  more Vercel project, imported the same way.
- **Custom domain**: **Settings → Domains**. Then set the environment variable `SITE_URL` to that address so
  canonical links and the sitemap use it (otherwise Vercel's own address is picked up automatically).
- **Analytics** (optional, cookieless): **Analytics** tab in the project.
- Pyodide (about 14 MB) is copied into `public/pyodide/` during the build, so the public site serves its own
  Python for code labs.
