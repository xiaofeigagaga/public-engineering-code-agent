# Public Engineering Code Agent

A privacy-safe engineering codebase debugging and documentation Agent.

This project scans a public or local engineering codebase, builds a lightweight project index, analyzes common build/runtime error logs, and generates a Markdown report. It is designed as a public demo project: it does not upload code, does not call external APIs, and does not require private project data.

## Features

- Scan Python, C/C++, CMake, YAML, XML, Markdown, shell, and ROS2-style project files.
- Identify important files such as `README.md`, `CMakeLists.txt`, `package.xml`, `requirements.txt`, and `setup.py`.
- Extract possible entry points, dependencies, ROS2 packages, and CMake targets.
- Analyze common error logs, including:
  - Python `ModuleNotFoundError`
  - CMake package missing errors
  - C/C++ header missing errors
  - Linker errors
  - ROS2 package discovery errors
  - permission errors
  - file path errors
  - network/proxy errors
  - OpenCV GUI/import errors
- Generate a Markdown codebase analysis report.

## Why this project exists

Large engineering projects often fail at the early stages of environment setup, dependency installation, compilation, and runtime debugging. New developers may spend a lot of time reading scattered configuration files and searching error messages manually.

This project demonstrates a simple Agent workflow:

```text
scan codebase -> build project index -> analyze error log -> locate related files -> suggest fixes -> generate documentation
```

The implementation is intentionally offline and rule-based, so it can be published safely and used as a transparent Agent demo.

## Installation

### Option 1: run directly

```bash
python run_agent.py --help
```

### Option 2: install as a package

```bash
pip install -e .
code-agent --help
```

## Quick Start

Create a demo project:

```bash
python run_agent.py demo --path ./demo_project
```

Scan the demo project:

```bash
python run_agent.py scan --path ./demo_project
```

Save the project index:

```bash
python run_agent.py scan --path ./demo_project --save-index index.json
```

Generate a Markdown report:

```bash
python run_agent.py doc --path ./demo_project --output PROJECT_REPORT.md
```

Analyze an error log:

```bash
python run_agent.py ask --path ./demo_project --log examples/logs/python_module_error.log
```

## Example error log

`examples/logs/python_module_error.log`:

```text
Traceback (most recent call last):
  File "main.py", line 1, in <module>
    import cv2
ModuleNotFoundError: No module named 'cv2'
```

Expected result: the Agent identifies a missing Python module, suggests checking the Python environment, installing dependencies, and verifying the import.

## Project Structure

```text
public-engineering-code-agent/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── run_agent.py
├── src/
│   └── code_agent/
│       ├── __init__.py
│       ├── __main__.py
│       └── agent.py
├── examples/
│   └── logs/
│       ├── python_module_error.log
│       ├── cmake_package_error.log
│       └── cpp_header_error.log
└── tests/
    └── test_basic.py
```

## Privacy and Safety

- No external API calls.
- No cloud upload.
- No private dataset required.
- Works on local/public repositories.
- Designed for public GitHub demonstration.

## Limitations

This is a lightweight demo Agent. It does not fully understand all source code semantics and does not replace a compiler, debugger, or full LLM-based code assistant. It is best used for project overview, common error classification, and first-pass debugging suggestions.

## License

MIT License.
