# Summary

<!-- What does this change do, and why? -->

## Related issues

<!-- e.g. Closes #123 -->

## Testing

<!-- How did you verify the change? -->

- [ ] `make check` passes locally (lint, tests, dependency audit)
- [ ] Added or updated tests for behavioural changes

## Documentation

- [ ] Updated the README for any installation, configuration, or command changes
- [ ] Updated docstrings for changed tool signatures or behaviour

## Security review

- [ ] No credentials, tokens, cookies, or real Accelo/customer data are included
- [ ] Tool inputs from the LLM are treated as untrusted (validated, no shell/eval, bound parameters)
- [ ] New write or delete tools are clearly documented and justified
- [ ] Changes do not broaden the default OAuth scope beyond `read(all)`
