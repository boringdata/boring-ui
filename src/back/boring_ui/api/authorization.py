"""Shared authorization utilities for permission/operation matching (bd-2j57.8).

Provides wildcard-aware permission matching logic used across:
- AuthContext (OIDC permissions)
- CapabilityAuthContext (capability tokens)
- CapabilityToken validation
"""


def has_scoped_access(required: str, granted: set[str]) -> bool:
    """Check if required permission/operation is granted by the set.

    Supports wildcard matching:
    - '*' grants all operations
    - 'namespace:*' grants all operations in namespace
    - Exact match for specific operations

    Args:
        required: Required permission/operation (e.g., 'files:read')
        granted: Set of granted permissions/operations

    Returns:
        True if required operation is granted, False otherwise

    Examples:
        >>> has_scoped_access('files:read', {'files:read'})
        True
        >>> has_scoped_access('files:read', {'files:*'})
        True
        >>> has_scoped_access('files:read', {'*'})
        True
        >>> has_scoped_access('files:read', {'git:*'})
        False
    """
    # Full wildcard
    if "*" in granted:
        return True

    # Exact match
    if required in granted:
        return True

    # Namespace wildcard (e.g., 'files:*' matches 'files:read')
    if ":" in required:
        namespace = required.split(":")[0] + ":*"
        if namespace in granted:
            return True

    return False
