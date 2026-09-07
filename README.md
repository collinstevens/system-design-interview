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
