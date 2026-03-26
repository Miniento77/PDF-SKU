class LabelPdfSkuError(Exception):
    """Base exception for the project."""


class ParseError(LabelPdfSkuError):
    """Raised when manual SKU input is malformed."""


class LayoutError(LabelPdfSkuError):
    """Raised when footer text cannot fit inside the configured bounds."""


class DependencyError(LabelPdfSkuError):
    """Raised when PDF dependencies are not installed."""

