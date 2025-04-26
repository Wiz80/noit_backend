import os
import sys
import click
import uvicorn
from alembic.config import Config
from alembic import command

@click.group()
def cli():
    """Management script for the Identity Verification Service"""
    pass

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, default=False, help='Enable auto-reload')
def runserver(host, port, reload):
    """Run the FastAPI development server"""
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )

@cli.command()
def db_init():
    """Initialize the database"""
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    click.echo("Database initialized!")

@cli.command()
@click.argument('message')
def db_migrate(message):
    """Create a new database migration"""
    config = Config("alembic.ini")
    command.revision(config, autogenerate=True, message=message)
    click.echo(f"Created new migration with message: {message}")

@cli.command()
def db_upgrade():
    """Upgrade database to the latest version"""
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    click.echo("Database upgraded!")

@cli.command()
@click.argument('revision', default='-1')
def db_downgrade(revision):
    """Downgrade database to a specific revision"""
    config = Config("alembic.ini")
    command.downgrade(config, revision)
    click.echo(f"Database downgraded to {revision}!")

if __name__ == '__main__':
    cli()