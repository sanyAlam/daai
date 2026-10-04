# Contributing

This is a portfolio archive with no promised maintenance schedule. Small,
well-explained fixes are welcome through GitHub pull requests.

Use Python 3.11 and Node 20. Follow the README installation instructions, run
the API and SDK tests and local demo, then run `npm ci`, `npm run lint`, and
`npm run build` in `apps/dashboard` for dashboard changes. Public CI needs no
private credentials and performs no deployment.

Keep runtime policy deterministic. Preserve workspace isolation and the
separation between governance and execution. Do not execute callbacks inside
`intercept()`. Keep examples synthetic and local; never commit environment
files, credentials, approval URLs, database dumps, or real customer payloads.
