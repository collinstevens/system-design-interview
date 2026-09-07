# System Design Interview

A place to exercise and review what I've read in _System Design Interview_.

Use this repo to revisit concepts, work through design exercises, and build small implementations to deepen my understanding of the material.

## Setup

Run these commands from the repository root:

```sh
mise install
mise exec -- bun install --frozen-lockfile
```

`mise` installs the pinned Bun, Node.js, TypeScript, and [hk](https://hk.jdx.dev/) versions and enables Git hooks. Bun manages all projects as [workspaces](https://bun.com/docs/pm/workspaces), with one root install and `bun.lock`. With mise activated, the `mise exec --` prefix is optional.

In PowerShell, use `mise.exe` instead of `mise` for the `mise exec -- ...` commands in this guide. The activated PowerShell wrapper can consume the `--` separator, causing Bun or hk flags to be interpreted as mise flags. Calling the executable directly preserves the arguments:

```powershell
mise.exe exec -- bun install --frozen-lockfile
mise.exe exec -- bun run --filter sliding-window-log demo alice
```

## Projects

The rate-limiting exercises have separate TypeScript projects backed by Redis. Each has its own demo and Docker Compose configuration.

| Project                                                             | Behavior                                                                    | Local Redis port |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------- |
| [Token bucket](projects/token-bucket/README.md)                     | Periodically refill tokens; admit requests while tokens remain.             | 6380             |
| [Leaking bucket](projects/leaking-bucket/README.md)                 | Queue requests in a bounded FIFO and release them at a fixed pace.          | 6382             |
| [Sliding window log](projects/sliding-window-log/README.md)         | Track individual attempt timestamps in a rolling window.                    | 6379             |

Run a project's scripts from its directory, or select it from the root:

```sh
mise exec -- bun run --filter sliding-window-log redis:up
mise exec -- bun run --filter sliding-window-log demo alice
mise exec -- bun run --filter sliding-window-log redis:down
```

## Shared tooling

Run these commands from the repository root:

```sh
bun run lint
bun run lint:fix
bun run fmt
bun run fmt:check
bun run check
bun run build
```

Linting and formatting cover the repository. Type checking and building run each workspace's `check` and `build` scripts. Shared TypeScript options live in `tsconfig.base.json`; projects supply their source and output paths.

Oxlint, Oxfmt, `@oxlint/plugins`, and Node.js types are installed once as root development dependencies. The TypeScript compiler comes from `mise.toml`. The root [dependency catalog](https://bun.com/docs/pm/catalogs) pins shared runtime dependencies such as Effect and Redis; each project declares the dependencies it uses with `"catalog:"`.

`.oxlintrc.json` enables correctness rules, Node.js globals, all 15 generic [anti-slop](tools/oxlint/anti-slop/README.md) rules, and the Effect `no-service-constructor-imports` rule. Both lint scripts reject warnings and errors. `.oxfmtrc.json` uses Oxfmt's default formatting settings. Generated `dist/` directories, dependencies, and vendored lint rules are excluded from linting and formatting.

The hk pre-commit hook formats supported files and applies safe lint fixes, stashing unstaged changes while it runs. The commit-msg hook enforces [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Run `mise exec -- hk check --all` to check linting and formatting together, or `mise exec -- hk fix --all` to apply fixes.

For editor integration, follow the official [Oxlint](https://oxc.rs/docs/guide/usage/linter/editors.html) and [Oxfmt](https://oxc.rs/docs/guide/usage/formatter/editors.html) setup guides. VS Code uses the `oxc.oxc-vscode` extension for both.

## Add an exercise

Create `projects/<exercise-name>/src/`, a README, and a `package.json` with a unique name. For example:

```json
{
  "name": "token-bucket",
  "private": true,
  "type": "module",
  "scripts": {
    "check": "mise exec -- tsc --noEmit",
    "build": "mise exec -- tsc",
    "demo": "bun run build && mise exec -- node dist/demo.js"
  },
  "dependencies": {
    "effect": "catalog:",
    "redis": "catalog:"
  }
}
```

Declare only the dependencies the exercise uses. Add new shared versions to the root `catalog` when needed. Keep any project-specific build steps, such as copying Lua scripts, in that project's scripts.

Add a `tsconfig.json`:

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist"
  },
  "include": ["src/**/*.ts"]
}
```

Add the implementation and any infrastructure it needs, then run `mise exec -- bun install` from the root and commit the updated root lockfile. The workspace glob and shared commands automatically include the new exercise. Add a link to its README in the project list above.
