from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
import os
import sys

# Ensure project root is importable
sys.path.append(os.getcwd())

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import the application's Base + models so autogenerate works
from app.database import Base, DATABASE_URL

# Import all models here so Alembic sees them
from app.models.tenant import Tenant
from app.models.depot import Depot
from app.models.vehicle import Vehicle
from app.models.team_member import TeamMember
from app.models.job import Job
from app.models.route import Route, RouteStop

# Alembic Config
config = context.config

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


# ----------------------------------------
# SAFETY CHECK: Ensure DATABASE_URL exists
# ----------------------------------------
if not DATABASE_URL:
    raise RuntimeError(
        "ERROR: DATABASE_URL is not set.\n"
        "Make sure it is defined in Render or your local .env file."
    )


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Update config with our DATABASE_URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # detects column type changes
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
