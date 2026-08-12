class RiotApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Riot API error {status_code}: {message}")


class RiotNotFoundError(RiotApiError):
    pass
