# Vendored anti-slop rules

Source: [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop/tree/e8c4880471b23ab7f216fba7b27d173a6ef07d4c), commit `e8c4880471b23ab7f216fba7b27d173a6ef07d4c`.

This directory contains unchanged copies of `src/index.ts`, the 15 generic rule implementations in `src/rules/`, their helpers in `src/shared/`, and the Effect plugin entry point and rule implementation in `src/effect/`. The upstream MIT license is included in `LICENSE`. Upstream tests are omitted.

All generic rules and `anti-slop-effect/no-service-constructor-imports` are enabled as errors with their default options in `../../../.oxlintrc.json`, without exceptions for project code. The Effect rule rejects named `make<CapabilityName>` imports from relative project modules outside test and spec files; runtime callers should import the owning Layer and yield the contextual service. Project code should avoid non-const type assertions to follow the repository's no-comments policy.

Oxlint and Oxfmt ignore this directory to preserve the upstream source. Keep `oxlint` and `@oxlint/plugins` pinned to the same exact version.

To update, copy the same source files and license from a reviewed upstream commit, update the source revision here, and reconcile the generic and Effect rule lists in `.oxlintrc.json`. Run `bun run lint`, `bun run fmt:check`, and `bun run check` from the repository root.
