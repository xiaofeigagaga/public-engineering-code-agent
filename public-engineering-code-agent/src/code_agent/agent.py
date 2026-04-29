#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Public Engineering Code Agent

A privacy-safe engineering code assistant that scans public/local codebases,
creates lightweight project indexes, analyzes common build/runtime logs, and
produces Markdown documentation.

This demo is fully offline and rule-based. It does not upload code or call any
external API, which makes it suitable for GitHub publication and classroom demos.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_EXTENSIONS = {
    ".py", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hh",
    ".cmake", ".txt", ".md", ".yaml", ".yml", ".xml", ".json",
    ".launch", ".sh",
}

IMPORTANT_FILENAMES = {
    "README.md", "readme.md", "CMakeLists.txt", "package.xml",
    "requirements.txt", "setup.py", "pyproject.toml", "environment.yml",
    "dockerfile", "Dockerfile", "Makefile",
}

IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", "build", "install", "log",
    "dist", "node_modules", ".pytest_cache", ".mypy_cache", ".venv", "venv",
}

MAX_FILE_READ_CHARS = 12000


@dataclass
class FileInfo:
    path: str
    extension: str
    size_bytes: int
    line_count: int
    is_important: bool
    summary: str


@dataclass
class ProjectIndex:
    root: str
    files: List[FileInfo]
    languages: Dict[str, int]
    important_files: List[str]
    entry_points: List[str]
    dependencies: List[str]
    ros2_packages: List[str]
    cmake_targets: List[str]


@dataclass
class ErrorAnalysis:
    error_type: str
    keywords: List[str]
    likely_causes: List[str]
    related_files: List[str]
    suggestions: List[str]
    verify_commands: List[str]


class SafeFileReader:
    @staticmethod
    def read_text(path: Path, max_chars: int = MAX_FILE_READ_CHARS) -> str:
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                return ""
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        except Exception:
            return ""

    @staticmethod
    def count_lines(text: str) -> int:
        return 0 if not text else text.count("\n") + 1


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def is_supported_file(path: Path) -> bool:
    return path.name in IMPORTANT_FILENAMES or path.suffix in SUPPORTED_EXTENSIONS


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


class ProjectScanner:
    """Scan a project and build a lightweight code index."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Project path does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.root}")

    def scan(self) -> ProjectIndex:
        files: List[FileInfo] = []
        languages: Dict[str, int] = {}
        important_files: List[str] = []
        entry_points: List[str] = []
        dependencies: List[str] = []
        ros2_packages: List[str] = []
        cmake_targets: List[str] = []

        for path in self.root.rglob("*"):
            if should_ignore(path) or not path.is_file() or not is_supported_file(path):
                continue

            rel = relative_path(path, self.root)
            text = SafeFileReader.read_text(path)
            ext = path.suffix if path.suffix else path.name
            languages[ext] = languages.get(ext, 0) + 1

            if path.name in IMPORTANT_FILENAMES:
                important_files.append(rel)
            if self._looks_like_entry_point(path, text):
                entry_points.append(rel)

            dependencies.extend(self._extract_dependencies(path, text))
            ros2_packages.extend(self._extract_ros2_packages(path, text))
            cmake_targets.extend(self._extract_cmake_targets(path, text))

            files.append(FileInfo(
                path=rel,
                extension=ext,
                size_bytes=path.stat().st_size,
                line_count=SafeFileReader.count_lines(text),
                is_important=path.name in IMPORTANT_FILENAMES,
                summary=self._summarize_file(path, text),
            ))

        return ProjectIndex(
            root=str(self.root),
            files=sorted(files, key=lambda f: f.path),
            languages=dict(sorted(languages.items(), key=lambda item: item[0])),
            important_files=sorted(set(important_files)),
            entry_points=sorted(set(entry_points)),
            dependencies=sorted(set(dependencies)),
            ros2_packages=sorted(set(ros2_packages)),
            cmake_targets=sorted(set(cmake_targets)),
        )

    def _summarize_file(self, path: Path, text: str) -> str:
        if path.name == "CMakeLists.txt":
            targets = self._extract_cmake_targets(path, text)
            packages = re.findall(r"find_package\(([^\s\)]+)", text)
            return f"CMake build configuration; targets={targets[:5]}; find_package={packages[:8]}"
        if path.name == "package.xml":
            package_match = re.search(r"<name>(.*?)</name>", text)
            deps = re.findall(r"<(?:depend|build_depend|exec_depend)>(.*?)</", text)
            pkg = package_match.group(1) if package_match else "unknown"
            return f"ROS2 package.xml; package={pkg}; deps={deps[:8]}"
        if path.name == "requirements.txt":
            deps = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
            return f"Python dependency file; deps={deps[:8]}"
        if path.suffix == ".py":
            funcs = re.findall(r"^def\s+([a-zA-Z_][\w]*)\s*\(", text, flags=re.MULTILINE)
            classes = re.findall(r"^class\s+([a-zA-Z_][\w]*)", text, flags=re.MULTILINE)
            return f"Python source; classes={classes[:5]}; functions={funcs[:8]}"
        if path.suffix in {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hh"}:
            includes = re.findall(r"#include\s+[<\"]([^>\"]+)[>\"]", text)
            classes = re.findall(r"class\s+([a-zA-Z_][\w]*)", text)
            return f"C/C++ source; includes={includes[:8]}; classes={classes[:5]}"
        if path.suffix in {".yaml", ".yml"}:
            keys = re.findall(r"^([a-zA-Z_][\w\-]*)\s*:", text, flags=re.MULTILINE)
            return f"YAML config; top_keys={keys[:8]}"
        if path.suffix == ".md":
            titles = re.findall(r"^#+\s+(.*)", text, flags=re.MULTILINE)
            return f"Markdown doc; titles={titles[:6]}"
        return "Text/configuration file"

    def _looks_like_entry_point(self, path: Path, text: str) -> bool:
        if path.name in {"main.py", "app.py", "train.py", "run.py"}:
            return True
        if path.suffix == ".py" and 'if __name__ == "__main__"' in text:
            return True
        if path.suffix in {".cpp", ".cc", ".cxx", ".c"} and re.search(r"int\s+main\s*\(", text):
            return True
        return path.name == "CMakeLists.txt" and "add_executable" in text

    def _extract_dependencies(self, path: Path, text: str) -> List[str]:
        deps: List[str] = []
        if path.name == "requirements.txt":
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(re.split(r"[=<>~! ]", line)[0])
        if path.name == "CMakeLists.txt":
            deps.extend(re.findall(r"find_package\(([^\s\)]+)", text))
        if path.name == "package.xml":
            deps.extend(re.findall(r"<(?:depend|build_depend|exec_depend|test_depend)>(.*?)</", text))
        if path.suffix == ".py":
            deps.extend(re.findall(r"^import\s+([a-zA-Z_][\w]*)", text, flags=re.MULTILINE))
            deps.extend(re.findall(r"^from\s+([a-zA-Z_][\w]*)\s+import", text, flags=re.MULTILINE))
        return deps

    def _extract_ros2_packages(self, path: Path, text: str) -> List[str]:
        if path.name != "package.xml":
            return []
        match = re.search(r"<name>(.*?)</name>", text)
        return [match.group(1).strip()] if match else []

    def _extract_cmake_targets(self, path: Path, text: str) -> List[str]:
        if path.name != "CMakeLists.txt":
            return []
        return re.findall(r"add_executable\s*\(\s*([^\s\)]+)", text) + re.findall(r"add_library\s*\(\s*([^\s\)]+)", text)


class ErrorAnalyzerAgent:
    """Rule-based build/runtime log analyzer."""

    def __init__(self, index: ProjectIndex):
        self.index = index

    def analyze(self, error_log: str) -> ErrorAnalysis:
        log = error_log.strip()
        lower = log.lower()
        if not log:
            return ErrorAnalysis("empty_log", [], ["No error log was provided."], [], ["Provide the full build or runtime log."], [])

        for func in [
            self._analyze_python_module_error,
            self._analyze_cmake_package_error,
            self._analyze_cpp_header_error,
            self._analyze_link_error,
            self._analyze_ros2_package_error,
            self._analyze_permission_error,
            self._analyze_file_not_found_error,
            self._analyze_network_error,
            self._analyze_opencv_error,
        ]:
            result = func(log, lower)
            if result:
                return result
        return self._generic_analysis(log)

    def _related_files_by_keywords(self, keywords: List[str], limit: int = 8) -> List[str]:
        scores: List[Tuple[int, str]] = []
        for f in self.index.files:
            text = f"{f.path} {f.summary}".lower()
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score:
                scores.append((score, f.path))
        scores.sort(key=lambda item: (-item[0], item[1]))
        return [path for _, path in scores[:limit]]

    def _analyze_python_module_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        match = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", log)
        if not match:
            return None
        module = match.group(1)
        return ErrorAnalysis(
            "python_module_not_found", [module, "requirements.txt", "venv"],
            [f"Python module `{module}` is not installed.", "The active Python environment may be different from the dependency environment."],
            self._related_files_by_keywords([module, "requirements", "setup.py", "pyproject"]),
            [f"Install the missing dependency: `python -m pip install {module}`.", "If requirements.txt exists, run `python -m pip install -r requirements.txt`.", "Check whether the correct virtual environment is activated."],
            ["python --version", "python -m pip list", f"python -c \"import {module}; print('ok')\""]
        )

    def _analyze_cmake_package_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "could not find a package configuration file" not in lower and "find_package" not in lower:
            return None
        package = "unknown_package"
        match = re.search(r"provided by\s+\"?([A-Za-z0-9_\-]+)\"?", log)
        if match:
            package = match.group(1)
        return ErrorAnalysis(
            "cmake_package_not_found", [package, "find_package", "CMAKE_PREFIX_PATH"],
            [f"CMake cannot find dependency `{package}`.", "The dependency is not installed or its prefix path is not configured."],
            self._related_files_by_keywords([package, "CMakeLists", "package.xml"]),
            ["Check the package name used by find_package().", "Install the missing dependency.", "For ROS2 projects, source ROS and the workspace setup files."],
            ["echo $CMAKE_PREFIX_PATH", f"ros2 pkg prefix {package}  # if this is a ROS2 package", "colcon build --symlink-install"]
        )

    def _analyze_cpp_header_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        match = re.search(r"fatal error:\s*([^:\n]+):\s*No such file or directory", log)
        if not match:
            return None
        header = match.group(1).strip()
        return ErrorAnalysis(
            "cpp_header_not_found", [header, "include", "target_include_directories"],
            [f"Header `{header}` was not found by the compiler.", "The include path may be missing from CMake."],
            self._related_files_by_keywords([header, "CMakeLists", "include"]),
            ["Check whether the header file exists.", "Add the correct include directory in CMakeLists.txt.", "Install the corresponding development package if it is a third-party header."],
            [f"find . -name '{Path(header).name}' -print", "grep -R \"target_include_directories\\|include_directories\" -n ."]
        )

    def _analyze_link_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "undefined reference" not in lower and "cannot find -l" not in lower:
            return None
        return ErrorAnalysis(
            "link_error", ["undefined reference", "target_link_libraries"],
            ["A function or library is missing during the link stage.", "A source file may not be included in the build target."],
            self._related_files_by_keywords(["CMakeLists", "target_link_libraries", "add_library"]),
            ["Check whether all implementation files are included in add_executable/add_library.", "Check target_link_libraries().", "Verify that function declarations and definitions match exactly."],
            ["grep -R \"target_link_libraries\\|add_library\\|add_executable\" -n ."]
        )

    def _analyze_ros2_package_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "package not found" not in lower and "unknown package" not in lower and "ros2 run" not in lower:
            return None
        return ErrorAnalysis(
            "ros2_package_error", ["ROS2", "package.xml", "ament", "colcon"],
            ["The ROS2 workspace may not be sourced.", "The package may not have been built or installed correctly."],
            self._related_files_by_keywords(["package.xml", "CMakeLists", "ament_package", "setup.py"]),
            ["Run `source /opt/ros/humble/setup.bash`.", "Build the workspace with `colcon build --symlink-install`.", "Run `source install/setup.bash` after building."],
            ["colcon list", "ros2 pkg list | head"]
        )

    def _analyze_permission_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "permission denied" not in lower:
            return None
        return ErrorAnalysis(
            "permission_denied", ["permission denied", "chmod", "dialout"],
            ["The current user lacks permission to execute a file or access a device."],
            self._related_files_by_keywords([".sh", "serial", "usb", "launch"]),
            ["For scripts, run `chmod +x script.sh`.", "For serial devices, check `/dev/ttyUSB*` permissions and user groups."],
            ["id", "groups", "ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null"]
        )

    def _analyze_file_not_found_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "no such file or directory" not in lower and "file not found" not in lower:
            return None
        return ErrorAnalysis(
            "file_not_found", ["path", "config", "file not found"],
            ["A referenced file path does not exist.", "The program may be running from a different working directory."],
            self._related_files_by_keywords(["path", "config", "launch", "yaml", "CMakeLists"]),
            ["Check whether the path in the log exists.", "Try an absolute path to exclude working-directory issues.", "For CMake/ROS2, verify install rules for resource files."],
            ["pwd", "find . -maxdepth 4 -type f | head -50"]
        )

    def _analyze_network_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if not any(k in lower for k in ["failed to connect", "connection refused", "connection timed out", "could not resolve host", "proxy"]):
            return None
        return ErrorAnalysis(
            "network_or_proxy_error", ["network", "proxy", "connection refused", "timeout"],
            ["Network access or proxy configuration failed.", "Proxy environment variables may point to an unreachable address."],
            self._related_files_by_keywords(["README", "Dockerfile", "requirements", "ExternalProject", "git"]),
            ["Check proxy environment variables.", "Unset invalid proxy variables.", "Check Git proxy settings."],
            ["env | grep -i proxy", "git config --global --get http.proxy", "curl -I https://github.com --connect-timeout 5"]
        )

    def _analyze_opencv_error(self, log: str, lower: str) -> Optional[ErrorAnalysis]:
        if "opencv" not in lower and "cv2" not in lower and "imshow" not in lower:
            return None
        return ErrorAnalysis(
            "opencv_error", ["OpenCV", "cv2", "imshow", "image"],
            ["OpenCV may be missing or the GUI environment may not support imshow().", "The input image may be empty or in an unexpected format."],
            self._related_files_by_keywords(["opencv", "cv2", "imshow", "image", "camera"]),
            ["Test OpenCV import.", "In headless environments, save debug images instead of using imshow().", "Check image shape, channel count, and empty state."],
            ["python -c \"import cv2; print(cv2.__version__)\"", "echo $DISPLAY"]
        )

    def _generic_analysis(self, log: str) -> ErrorAnalysis:
        keywords = self._extract_keywords(log)
        return ErrorAnalysis(
            "generic_error", keywords,
            ["The error type is unclear and needs more context.", "It may relate to dependencies, paths, build cache, or runtime environment mismatch."],
            self._related_files_by_keywords(keywords),
            ["Focus on the first real error in the log.", "Search the codebase for file names, function names, or package names from the log.", "Clean build cache and rebuild if appropriate."],
            ["grep -R \"keyword\" -n .", "colcon build --event-handlers console_direct+  # for ROS2 projects"]
        )

    def _extract_keywords(self, log: str) -> List[str]:
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_\-\.]{2,}", log)
        stop_words = {"error", "warning", "failed", "found", "file", "line", "from", "this", "that", "with", "make", "cmake", "build"}
        result: List[str] = []
        for word in words:
            if word.lower() not in stop_words and word not in result:
                result.append(word)
            if len(result) >= 10:
                break
        return result


class DocumentationAgent:
    def __init__(self, index: ProjectIndex):
        self.index = index

    def generate_markdown(self) -> str:
        lines: List[str] = [
            "# Engineering Codebase Analysis Report", "",
            "## 1. Project Overview", "",
            f"- Project path: `{self.index.root}`",
            f"- Scanned files: `{len(self.index.files)}`",
            f"- Important configuration files: `{len(self.index.important_files)}`", "",
            "## 2. Language and File Type Distribution", "",
        ]
        if self.index.languages:
            lines.extend(f"- `{ext}`: {count}" for ext, count in self.index.languages.items())
        else:
            lines.append("- No supported code files detected.")
        lines.extend(["", "## 3. Important Files", ""])
        lines.extend((f"- `{f}`" for f in self.index.important_files),) if False else None
        if self.index.important_files:
            lines.extend(f"- `{f}`" for f in self.index.important_files)
        else:
            lines.append("- No README/CMake/package/requirements files detected.")
        lines.extend(["", "## 4. Possible Entry Points", ""])
        lines.extend(f"- `{f}`" for f in self.index.entry_points) if self.index.entry_points else lines.append("- No obvious entry point detected.")
        lines.extend(["", "## 5. Dependencies", ""])
        lines.extend(f"- `{dep}`" for dep in self.index.dependencies[:80]) if self.index.dependencies else lines.append("- No dependencies extracted automatically.")
        if self.index.ros2_packages:
            lines.extend(["", "## 6. ROS2 Packages", ""])
            lines.extend(f"- `{pkg}`" for pkg in self.index.ros2_packages)
        if self.index.cmake_targets:
            lines.extend(["", "## 7. CMake Targets", ""])
            lines.extend(f"- `{target}`" for target in self.index.cmake_targets)
        lines.extend(["", "## 8. File Summaries", "", "| File | Lines | Summary |", "|---|---:|---|"])
        for f in self.index.files[:150]:
            lines.append(f"| `{f.path}` | {f.line_count} | {f.summary.replace('|', '\\|')} |")
        if len(self.index.files) > 150:
            lines.append(f"| ... | ... | {len(self.index.files) - 150} additional files omitted. |")
        lines.extend(["", "## 9. Suggested Debugging Workflow", "", "1. Read README and identify the expected run path.", "2. Check dependencies such as requirements.txt, package.xml, and CMakeLists.txt.", "3. When a build fails, locate the first real error rather than the final summary line.", "4. For ROS2 projects, source ROS and the current workspace.", "5. Rebuild after cleaning cache if stale build artifacts may affect the result.", ""])
        return "\n".join(lines)


class EngineeringCodeAgent:
    def __init__(self, project_path: str):
        self.index = ProjectScanner(project_path).scan()

    def print_summary(self) -> None:
        print("\n=== Project Scan Summary ===")
        print(f"Project path: {self.index.root}")
        print(f"File count: {len(self.index.files)}")
        print(f"File types: {json.dumps(self.index.languages, ensure_ascii=False)}")
        print("\nImportant files:")
        print("\n".join(f"  - {f}" for f in self.index.important_files) or "  - None")
        print("\nPossible entry points:")
        print("\n".join(f"  - {f}" for f in self.index.entry_points) or "  - None")

    def analyze_log(self, error_log: str) -> ErrorAnalysis:
        return ErrorAnalyzerAgent(self.index).analyze(error_log)

    def generate_doc(self) -> str:
        return DocumentationAgent(self.index).generate_markdown()

    def save_index(self, output: str) -> None:
        Path(output).write_text(json.dumps(asdict(self.index), ensure_ascii=False, indent=2), encoding="utf-8")


class ConsoleRenderer:
    @staticmethod
    def print_error_analysis(result: ErrorAnalysis) -> None:
        print("\n=== Agent Error Analysis ===")
        print(f"Error type: {result.error_type}")
        for title, items in [
            ("Keywords", result.keywords),
            ("Likely causes", result.likely_causes),
            ("Related files", result.related_files),
            ("Suggestions", result.suggestions),
            ("Verification commands", result.verify_commands),
        ]:
            print(f"\n{title}:")
            print("\n".join(f"  - {item}" for item in items) or "  - None")


def create_demo_project(path: str) -> None:
    root = Path(path)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text('''import cv2\nimport numpy as np\n\ndef main():\n    print("demo project running")\n    img = np.zeros((300, 300, 3), dtype=np.uint8)\n    cv2.imwrite("demo_output.png", img)\n\nif __name__ == "__main__":\n    main()\n''', encoding="utf-8")
    (root / "CMakeLists.txt").write_text('''cmake_minimum_required(VERSION 3.10)\nproject(demo_cpp_project)\n\nfind_package(OpenCV REQUIRED)\n\nadd_executable(demo_node src/main.cpp)\ntarget_link_libraries(demo_node ${OpenCV_LIBS})\n''', encoding="utf-8")
    (root / "src" / "main.cpp").write_text('''#include <iostream>\n#include <opencv2/opencv.hpp>\n\nint main() {\n    std::cout << "demo cpp project" << std::endl;\n    cv::Mat img(300, 300, CV_8UC3);\n    return 0;\n}\n''', encoding="utf-8")
    (root / "README.md").write_text("# Demo Project\n\nA tiny public project for testing the Engineering Code Agent.\n", encoding="utf-8")
    (root / "requirements.txt").write_text("opencv-python\nnumpy\n", encoding="utf-8")
    print(f"Demo project created: {root.resolve()}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Public Engineering Code Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a project and print a summary")
    scan_parser.add_argument("--path", required=True, help="Project path")
    scan_parser.add_argument("--save-index", default=None, help="Save project index as JSON")

    ask_parser = subparsers.add_parser("ask", help="Analyze an error log")
    ask_parser.add_argument("--path", required=True, help="Project path")
    ask_parser.add_argument("--log", required=True, help="Error log file")

    doc_parser = subparsers.add_parser("doc", help="Generate a Markdown analysis report")
    doc_parser.add_argument("--path", required=True, help="Project path")
    doc_parser.add_argument("--output", default="PROJECT_REPORT.md", help="Output Markdown path")

    demo_parser = subparsers.add_parser("demo", help="Create a demo project")
    demo_parser.add_argument("--path", default="./demo_project", help="Demo project output path")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    if args.command == "demo":
        create_demo_project(args.path)
        return

    agent = EngineeringCodeAgent(args.path)
    if args.command == "scan":
        agent.print_summary()
        if args.save_index:
            agent.save_index(args.save_index)
            print(f"\nIndex saved to: {args.save_index}")
    elif args.command == "ask":
        error_log = Path(args.log).read_text(encoding="utf-8", errors="ignore")
        ConsoleRenderer.print_error_analysis(agent.analyze_log(error_log))
    elif args.command == "doc":
        Path(args.output).write_text(agent.generate_doc(), encoding="utf-8")
        print(f"Report generated: {args.output}")


if __name__ == "__main__":
    main()
