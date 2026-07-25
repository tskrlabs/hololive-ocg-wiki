# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Repo state

This repo uses the canonical strings unmodified — no remapping. As of setup, only
`wontfix` exists in GitHub (it ships as a default label); the other four have not been
created yet.

If applying a label fails because it doesn't exist, create it first:

```bash
gh label create needs-triage    --description "Maintainer needs to evaluate" --color FBCA04
gh label create needs-info      --description "Waiting on reporter"          --color D4C5F9
gh label create ready-for-agent --description "Fully specified, AFK-ready"   --color 0E8A16
gh label create ready-for-human --description "Needs human implementation"   --color 1D76DB
```
