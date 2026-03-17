class DimensigonMCPError(Exception):
    pass


class AuthenticationError(DimensigonMCPError):
    pass


class DimensigonAPIError(DimensigonMCPError):
    def __init__(self, status_code: int, message: str, endpoint: str):
        self.status_code = status_code
        self.message = message
        self.endpoint = endpoint
        super().__init__(f"API error {status_code} on {endpoint}: {message}")


class DimensigonConnectionError(DimensigonMCPError):
    pass
