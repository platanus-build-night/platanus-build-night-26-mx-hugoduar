# seed_db tool

You are writing a tiny Python tool named `seed_db` for the Noctua project.

The tool will be invoked as: `python tool.py <json-args>`.
It receives args like `{"rows": 3}` and must seed a Postgres database
running at `postgresql://noctua:noctua@host.docker.internal:5432/noctua` with `rows`
sample rows in a table called `widget` (`id serial primary key, name text`).

Constraints:
- Use only stdlib + psycopg2-binary.
- Top-level callable must be `def call(args: dict, sandbox=None) -> dict` returning {"inserted": N}.
- When executed as `__main__`, parse argv[1] as json, call `call(args)`, print json result.

Return ONLY the Python source — no markdown fences, no commentary.
