"""Structured failures and bounded JSON validation, extracted from monkey."""
import math


class BeaverError(ValueError):
    def __init__(self, code, location, message):
        super().__init__(f"{code} at {location}: {message}")
        self.code, self.location, self.message = code, str(location), message

    def as_dict(self):
        return dict(code=self.code, location=self.location, message=self.message)


def fail(code, location, message):
    raise BeaverError(code, location, message)


def budget(document, max_depth=96, max_nodes=500000):
    pending = [(document, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if isinstance(value, float) and not math.isfinite(value):
            fail("INVALID_NUMBER", "$", "Non-finite number")
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError:
                fail("INVALID_UNICODE", "$", "Unpaired Unicode surrogate")
        if depth > max_depth or count > max_nodes:
            fail("BUDGET_EXCEEDED", "$", "Depth or value budget exceeded")
        if isinstance(value, list):
            pending.extend((x, depth + 1) for x in value)
        elif isinstance(value, dict):
            pending.extend((x, depth + 1) for pair in value.items() for x in pair)
