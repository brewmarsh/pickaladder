with open("tests/test_security.py", "r") as f:
    content = f.read()

replacement = """    def test_rate_limiting(self) -> None:
        \"\"\"Verify that rate limiting blocks excessive requests.\"\"\"
        from pickaladder.core.security import _rate_limit_storage
        self.app.config["TEST_RATE_LIMITING"] = True

        _rate_limit_storage.clear()"""

content = content.replace("""    def test_rate_limiting(self) -> None:
        \"\"\"Verify that rate limiting blocks excessive requests.\"\"\"
        from pickaladder.core.security import _rate_limit_storage

        _rate_limit_storage.clear()""", replacement)

with open("tests/test_security.py", "w") as f:
    f.write(content)
