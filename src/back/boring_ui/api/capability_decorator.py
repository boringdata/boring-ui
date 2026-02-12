"""Capability-based route authorization decorator (bd-1adh.6.2).

Provides decorators for routes that require capability-based authorization
to ensure internal /internal/* routes enforce access control.
"""

from functools import wraps
from fastapi import Request, HTTPException, status
from typing import Callable, Any
import logging


logger = logging.getLogger(__name__)


def require_capability(required_operations: str | list[str] | None = None) -> Callable:
    """Decorator to enforce capability-based authorization on routes.

    Checks that request has valid CapabilityAuthContext in request.state
    and that the context has the required operations.

    Usage:
        @router.get("/files")
        @require_capability("files:read")
        async def list_files(request: Request):
            ...

        @router.post("/git/commit")
        @require_capability(["git:read", "git:write"])
        async def commit(request: Request):
            ...

    Args:
        required_operations: Operation(s) required for this route.
            Can be:
            - None: Route requires auth but any operation
            - str: Single operation required (e.g., "files:read")
            - list[str]: Any of the listed operations required

    Returns:
        Decorator function
    """
    # Normalize to list
    if required_operations is None:
        operations_list = []
    elif isinstance(required_operations, str):
        operations_list = [required_operations]
    else:
        operations_list = list(required_operations)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs) -> Any:
            # Try to find request in kwargs
            if request is None:
                # Look through args for Request
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                logger.error(
                    f"@require_capability decorator used on route without Request parameter"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal error: request context not available",
                )

            # Check if capability context exists
            capability_context = getattr(request.state, "capability_context", None)
            if capability_context is None:
                logger.warning(
                    f"Missing capability context for {request.method} {request.url.path}. "
                    f"Capability auth middleware may not be active."
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Capability authorization required",
                    headers={"WWW-Authenticate": 'Bearer realm="boring-ui-sandbox"'},
                )

            # Check required operations if specified
            if operations_list:
                has_operation = any(
                    capability_context.has_operation(op) for op in operations_list
                )
                if not has_operation:
                    logger.warning(
                        f"Insufficient capabilities: required {operations_list}, "
                        f"got {capability_context.operations}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions for operations: {operations_list}",
                    )

            # Call the actual route handler
            return await func(*args, request=request, **kwargs)

        return wrapper

    return decorator


def get_capability_context(request: Request):
    """Extract capability context from request.

    Raises HTTPException(401) if context not available.

    Args:
        request: FastAPI Request

    Returns:
        CapabilityAuthContext if available

    Raises:
        HTTPException: 401 if no context
    """
    context = getattr(request.state, "capability_context", None)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Capability authorization required",
        )
    return context
