# Publishing Automation Auditor MCP

The **official MCP Registry** lists server metadata. It **does not** host the Python package or execute the server.

## Before releasing

- Confirm GitHub Actions tests are green, including the real stdio MCP client test.
- Ensure `pyproject.toml` version and `server.json` version and package version are identical.
- Verify the README contains the exact `mcp-name: io.github.ahamdjin/automation-auditor-mcp` string (this is how the Registry verifies ownership of the PyPI package).
- Review exported behavior; this is static, best-effort analysis, not a security certificate.

## PyPI trusted publishing: one-time owner setup

1. Sign in to [PyPI](https://pypi.org/) or create an account and verify email/2FA as required.
2. If the PyPI project does not exist, go to **Publishing → Add a new pending publisher** in PyPI's account settings. If it exists under your own account, open project settings and add a trusted publisher there.
3. Enter:
   - Owner: `ahamdjin`
   - Repository: `automation-auditor-mcp`
   - Workflow filename: `publish-pypi.yml`
   - Environment name: `pypi`
   - Project name (for pending publishers): `automation-auditor-mcp`
4. In your GitHub repository, create an environment named **pypi** under **Settings → Environments**. Optionally require reviewers (recommended).
5. After steps above and successful CI, create a GitHub **release with tag v0.1.0**, targeting the vetted main commit. Publishing that release runs `publish-pypi.yml` and, after any environment approvals, uploads the version to PyPI via short-lived OIDC. There are no password/token secrets in GitHub.

**Do not publish a GitHub release until PyPI Trusted Publishing has been set up.**

## Registry publication

After the package exists at https://pypi.org/project/automation-auditor-mcp/0.1.0/:

1. Install the official `mcp-publisher` CLI: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx
2. From this repository, run `mcp-publisher validate server.json`.
3. Run `mcp-publisher login github` and complete the device authorization as `ahamdjin`. Do **not** share your authorization code or authentication token.
4. Run `mcp-publisher publish server.json`.
5. Check `https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.ahamdjin/automation-auditor-mcp`.

The registration name must match the README marker and GitHub-auth namespace. Initial publication requires your account authentication; the repository does not automatically publish to the Registry.

For a future version bump, update package metadata, `server.json` and CHANGELOG together, create a new vetted release tag, and republish registry metadata after the new PyPI version exists.

Official docs: [PyPI ownership verification](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx) · [Publisher quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx) · [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
