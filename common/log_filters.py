import logging
import re

# Any 10-digit Indian mobile number (optionally inside a longer string such as a URL).
_MOBILE = re.compile(r"(?<!\d)[6-9]\d{5}(\d{4})(?!\d)")


class MaskMobileFilter(logging.Filter):
    """Masks mobile numbers in log lines, keeping only the last 4 digits."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return True
        masked = _MOBILE.sub(lambda m: "******" + m.group(1), message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True
