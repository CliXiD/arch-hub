# Feedback 1

From @CliXiD after the job escalated.

User (via Discord): "Feed back แก้ตามที่แนะนำได้เลย" ("Feedback: fix it as recommended").

The recommendation they accepted (from the orchestrator, quoted):
The seeded `allowed` kind pairs leave a gap. SPEC-app-focus-view-02 and its Interfaces say a `routes_via` chain ends at the target's network or at the target node itself (e.g. `payments-api → vpc-prod → landing-zone → direct-connect → core-banking (on-prem)`), so `routes_via` must also allow network → application and network → external. Also add infrastructure → network for `routes_via` (e.g. an RDS database inside a VPC). Fix the seed migration on this branch (it is not merged yet, so editing 00003 on the branch is fine), the sample graph if it should use the new pairs (e.g. `direct-connect` routes_via `core-banking`), tests and the spec's allowed-pairs table, then push and update build.md.
