# Security

This archived project is provided without a production security or maintenance
commitment. The public showcase is static and has no writable governance API.

Report vulnerabilities privately through this repository's GitHub
**Security > Report a vulnerability** feature. Do not include secrets or
personal data in public issues. No response-time commitment is offered.

An approval authorizes a cooperative client to execute; it does not enforce
control of arbitrary code. Treat payloads and execution reports as client
claims. Production self-hosters must isolate their database, configure
authentication, use unique secret peppers, disable development shortcuts,
and maintain dependencies. Never expose privileged Supabase credentials in
browser code.

The source release upgrades Next.js to 15.5.27 and overrides PostCSS with the
patched direct dependency. The npm runtime-only audit reports zero known
vulnerabilities. The full audit still reports seven high-severity entries in
development tooling, all rooted in the `braces` pattern parser used by Tailwind
and ESLint dependencies. Do not build untrusted source or process untrusted
glob patterns with this archive's tooling. These packages are not used by the
static public showcase. A production self-hosting release requires further
dependency maintenance and full integration verification.
