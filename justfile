create-migration name='':
    uv run alembic revision --autogenerate -m "{{name}}"

migrate:
    uv run alembic upgrade head 

test:
    pytest
