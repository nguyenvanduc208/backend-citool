from autotest.models import BROWSER_CHOICES

def validate_browser(value):
    valid_values = [key for key, _ in BROWSER_CHOICES]
    if not isinstance(value, str) or not value.islower():
        return value

    browsers = value.split(',')
    invalid_browser = []
    for b in browsers:
        if b not in valid_values:
            invalid_browser.append(b)
    return invalid_browser
