# System Design Interview

A place to exercise and review what I've read in _System Design Interview_.

Use this repo to revisit concepts, work through design exercises, and build small implementations to deepen my understanding of the material.

## Setup

Run these commands from the repository root:

```sh
mise install
mise exec -- bun install --frozen-lockfile
```

In PowerShell, use `mise.exe exec --` to preserve command arguments.

Bun manages exercises in `projects/*` as workspaces with one root install
and lockfile. mise pins Bun, Node.js, TypeScript, Python, and hk. Shared
TypeScript options live in `tsconfig.base.json`; each exercise supplies its
own source and output paths.

Run `bun run check` or `bun run build` from the root once an exercise has
been added with the corresponding workspace scripts.

## Shared tooling

Run these commands from the repository root:

```sh
bun run lint
bun run lint:fix
bun run fmt
bun run fmt:check
```

Oxlint and Oxfmt are shared development dependencies. Linting rejects
warnings and errors, including all 15 generic anti-slop rules and the
Effect `no-service-constructor-imports` rule. The vendored rules include
their license and [source revision](tools/oxlint/anti-slop/README.md).
Generated output, dependencies, and vendored rules are excluded from checks.

mise installs the hk hooks. The pre-commit hook formats files and applies
safe lint fixes while preserving unstaged changes; the commit-msg hook
enforces Conventional Commits. Run `mise exec -- hk check --all` or
`mise exec -- hk fix --all` to check or fix formatting and linting together.
