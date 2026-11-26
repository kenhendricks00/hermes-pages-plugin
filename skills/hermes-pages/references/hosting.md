# Optional hosting, not a dependency

Rendering requires only Python 3.10+ and works offline. Static files can be hosted anywhere. Cloudflare Pages is the guided free option, using a dedicated Direct Upload project and its included `pages.dev` address. Custom domains are optional. Buying a domain is not free merely because Pages hosting has a free tier.

Official sources consulted for this release:
- https://developers.cloudflare.com/pages/get-started/direct-upload/
- https://developers.cloudflare.com/pages/platform/limits/
- https://developers.cloudflare.com/workers/wrangler/install-and-update/

The current Free plan docs list 500 builds/month, one concurrent build, 20,000 files/site, 25 MiB per asset, 100 projects/account (soft limit), and 100 custom domains/project. Direct Upload sends prebuilt static files; it does not run a hosted build. Do not describe any quota as unlimited or assume the build allowance guarantees an equal upload entitlement. Dashboard drag-and-drop supports 1,000 files; Wrangler supports 20,000. Retention is 30 days except the most recent 100 deployments and current production deployment are kept. Older preview links can disappear. Recheck current docs for changes.

This package does not use Functions, Workers, databases, DNS APIs or paid resources. Functions have separate Workers quotas and billing if added later. No hosting account is created by install or setup.

## User-driven onboarding

Use existing Wrangler if installed. Otherwise follow official instructions for a manually approved **local**, not global, installation in a separate tools directory. Supply its executable using `publish --wrangler <path>`. The tool never downloads Wrangler, automatically runs npx, reads token files, logs in on your behalf or changes account settings.

In your own interactive terminal:

```sh
wrangler login
wrangler pages project create YOUR-NEW-PROJECT --production-branch main
```

The first command opens Cloudflare OAuth. Complete that screen yourself. Do not paste tokens into chat. Creation is an explicit account action, not part of local setup. Choose a new dedicated project, not your personal site. Direct Upload projects cannot later switch to Git integration; create a separate project if you want a different deployment model.

Run the renderer's `publish --project YOUR-NEW-PROJECT --dry-run`, review its complete file list, then `publish --project YOUR-NEW-PROJECT --confirm-public`. Everything in the generated library is public. The exact production hostname can include an extra suffix if your desired name is taken. Use the URL Wrangler actually reports, fetch it, and check its content. No external upload is performed by dry-run. Publisher subprocess tests are mocks, not evidence of live deployment.

Alternatively drag the workspace's `public` folder into a **new** Pages project in the Cloudflare dashboard. This manual route uploads every file you drop, unlike the CLI's managed-only staging. Inspect the directory first and never include secrets. Do not drop the workspace root.

## Privacy and optional access control

A `pages.dev` address is public. Hiding the index or choosing a random slug does not secure a document. This plugin implements no password gate. Optional Cloudflare Access or another authenticated host requires a separate, deliberate configuration and may have its own limits or pricing. Verify protection on the exact public URLs before storing private material. Do not assume the default pages.dev hostname is protected just because a custom domain is.

Deleting local files does not erase old Cloudflare deployments or cached copies. If sensitive data was uploaded, remove affected deployments through Cloudflare and consider the data exposed. The utility has no remote deletion command.
