"""GitHub connection: sign-in, credential methods and repository authority (DEC-21b).

The contracts are ``docs/architecture/GITHUB_CONNECTION_SPEC.md``. Connecting
grants nothing by itself: every credential reaches git or the API only through
:class:`raiker.runtime.git_credential.GitCredentialBroker`, under a grant.
"""
