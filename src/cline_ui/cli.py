import click
from .app import app

@click.group()
def main():
    """A web-based UI for interacting with the Cline VS Code extension."""
    pass

@main.command()
def start():
    """Starts the Cline UI web server."""
    app.run(debug=True)

if __name__ == "__main__":
    main()
