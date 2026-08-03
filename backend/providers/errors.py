"""Shared provider exceptions."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base exception for external provider failures."""


class ProviderConfigError(ProviderError):
    """Raised when provider configuration is missing or invalid."""


class ProviderRequestError(ProviderError):
    """Raised when a provider request fails before receiving a valid response."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an error or malformed payload."""
