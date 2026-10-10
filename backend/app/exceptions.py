"""Application exceptions.

Every error is rendered by the handler in ``app.main`` as::

    {"detail": "<machine/dev friendly>", "message": "<optional playful Tanglish line>"}

``RateLimitError`` additionally sets a ``Retry-After`` header.
"""


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    default_detail: str = "Internal server error"
    default_message: str | None = (
        "Ayyo, server-la edho problem. Konjam neram kazhichu try pannunga."
    )

    def __init__(
        self,
        detail: str | None = None,
        message: str | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.detail = detail or self.default_detail
        self.message = message if message is not None else self.default_message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = 400
    default_detail = "Bad request"
    default_message = "Indha link sari illa machan."


class UnauthorizedError(AppError):
    status_code = 401
    default_detail = "Not authenticated"
    default_message = "Login pannunga machan, appo dhaan idhu work aagum."


class ForbiddenError(AppError):
    status_code = 403
    default_detail = "Forbidden"
    default_message = "Idhu unga area illa machan."


class NotFoundError(AppError):
    status_code = 404
    default_detail = "Not found"
    default_message = "Thedi thedi paathen, kaanom!"


class UnprocessableError(AppError):
    status_code = 422
    default_detail = "Unprocessable entity"
    default_message = "Article-ae kaanom!"


class RateLimitError(AppError):
    status_code = 429
    default_detail = "Rate limit exceeded"
    default_message = "Konjam slow-a po machan! Roast oven cool aaganum."

    def __init__(
        self,
        detail: str | None = None,
        message: str | None = None,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(detail, message)
        self.retry_after = retry_after


class UpstreamError(AppError):
    status_code = 502
    default_detail = "Upstream service error"
    default_message = "Server konjam tired, try again."
