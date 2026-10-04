1. Modify `pickaladder/admin/routes.py` to fix the `ModuleNotFoundError` for `faker`.
   - Remove the global import `from faker import Faker`.
   - In the `generate_users` function, add an optional import block:
     ```python
     try:
         from faker import Faker
     except ImportError:
         Faker = None  # type: ignore
     ```
   - Before using `Faker()`, check if `Faker` is not `None`. If it is `None`, flash a message and redirect instead of raising an error.
   - Update `db, fake, new_users = firestore.client(), Faker(), []` to only instantiate `Faker()` if it exists.
2. Read the modified `pickaladder/admin/routes.py` file to visually verify the changes.
3. Run tests using `uv run pytest tests/` to confirm that the `faker` dependency issue is resolved in testing environments without `faker` installed.
4. Run `uv run ruff format` and `uv run ruff check` to ensure styling and linting checks pass.
5. Create a PR with the fix.
