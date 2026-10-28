# Contributing

Start with the setup and checks in the README. Open a focused issue describing the workflow or
bug before broad architectural changes. Keep changes small and include tests for safety-sensitive
behavior. Broker fixtures must be synthetic or carefully sanitized and contain no account details.

New adapters need explicit capabilities, documented market/asset scope, normalized decimal values,
credential-free mocked tests, and clear environment labels. Unsupported assets should fail clearly.
Remote execution, human approval, risk and compliance work require a dedicated design review.
