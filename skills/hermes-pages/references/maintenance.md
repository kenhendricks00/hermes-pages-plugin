# Release and catalog checklist

1. Keep all source, templates, fixtures and screenshots generic. Never seed a public repository from a personal site's pages, JSON indexes, history, middleware, browser profiles or credentials.
2. Exercise setup in a fresh temporary workspace, render Markdown and trusted HTML, repeat setup/render, and test explicit updates. Assert that unmanaged files, edited managed files and symlinks fail closed. Test subprocess construction with mocks and label it as mocked.
3. Capture light, dark and phone screenshots using an already available LOCAL headless browser. Do not use a hosted browser merely for documentation screenshots. Test actual action buttons, print output and unsupported speech behavior. Keep tooling out of runtime dependencies.
4. Run unit tests, syntax checks, and `hermes plugins validate <repo> --install-deps`. Read cautions instead of treating the exit status as the whole review. A portable skill package uses plugin.json and does not need runtime hooks or core imports.
5. Before publishing, inspect every tracked path, the staged diff, and public examples for private domains, local usernames, tokens and user content. No generated workspaces or bytecode in git.
6. Push the public plugin first and verify its visibility and exact full commit SHA through GitHub. Pin source, banner and screenshots to that exact commit.
7. Use a separate upstream-main clone for the catalog submission. Add only plugin-catalog/hermes-pages.yaml. Follow the CURRENT canonical catalog README schema, run its validation/tests, and disclose filesystem reads/writes, explicit Wrangler subprocesses, OAuth ownership, network destinations and public uploads in the PR.
8. Push to an actual public fork and open a PR against upstream main. Read back the PR head/base and changed-file list. Never claim Marketplace availability before a maintainer merges. Updates require a new reviewed SHA-bump PR, not a self-updater.
9. Report the repository URL, exact pin, PR URL, actual test output, absolute local paths, and whether a real deployment was verified. Local rendering plus mocked upload is not live hosting.
