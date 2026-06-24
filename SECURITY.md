# Security Policy

## Reporting a Vulnerability

Agent Mill takes security seriously. If you discover a security vulnerability, please report it privately.

**Do not** report security vulnerabilities through public GitHub issues.

Instead, send details to the maintainers via:
- GitHub Security Advisory: https://github.com/Sugers955/agent-mill/security/advisories/new

Please include:
- Type of vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

You should receive a response within 48 hours. We will keep you informed of the fix progress.

## Scope

The following are covered by this security policy:

- The Agent Mill application code
- Authentication and authorization mechanisms
- API security
- Data encryption and storage

## Supported Versions

| Version | Supported |
|:--------|:---------:|
| latest  | ✅ |

## Security Measures

Agent Mill implements 7 security layers:

1. Tool whitelist (runtime)
2. System prompt safety prefix (model layer)
3. Input regex filtering (gateway, 12 rules)
4. Skill static scanning (upload time)
5. File cwd sandbox (SDK layer)
6. Download token (egress)
7. API Key encryption (Fernet)
