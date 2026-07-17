"""Search the OMIM API by keyword and save the results.

Run this file directly to use it. See README.md for the operator guide.
"""

import configparser


def load_api_key(config_path):
    """Return the saved API key, or None if there is no usable key."""
    parser = configparser.ConfigParser()
    read_files = parser.read(config_path)
    if not read_files:
        return None
    key = parser.get("omim", "api_key", fallback="")
    key = key.strip()
    if key == "":
        return None
    return key


def save_api_key(config_path, api_key):
    """Write the API key to the config file, creating it if needed."""
    parser = configparser.ConfigParser()
    parser["omim"] = {"api_key": api_key.strip()}
    with open(config_path, "w", encoding="utf-8") as config_file:
        parser.write(config_file)
