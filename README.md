# Cline UI

A web-based user interface for interacting with the [Cline](https://github.com/cline/cline) VS Code extension CLI.

## Features

- **Web Interface**: A clean, responsive web interface built with Flask and Bootstrap.
- **Query History**: Keeps a history of your queries and the responses from Cline.
- **Real-time Updates**: Visual feedback while Cline is processing your request.
- **Clipboard Integration**: Easily copy queries and responses to your clipboard.
- **Settings**: Configure the path to your Cline executable.

## Prerequisites

- Python 3.8+
- [Cline](https://github.com/cline/cline) installed and available in your system.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hissain/cline-ui.git
   cd cline-ui
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r src/cline_ui.egg-info/requires.txt
   # OR
   pip install flask click sqlalchemy
   ```

## Usage

1. Start the application:
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)
   python -m src.cline_ui.cli start
   ```

2. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. Enter your query in the text area and click "Submit".

## Configuration

If Cline is not found automatically, go to the **Settings** page in the UI and manually enter the path to the `cline` executable.

## License

[MIT](LICENSE)
