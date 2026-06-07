import re
import subprocess
import tempfile
from pathlib import Path
from shutil import which
from typing import Any


SUPPORTED_LANGUAGES = {
    "python",
    "python3",
    "javascript",
    "js",
    "node",
    "typescript",
    "ts",
    "java",
    "cpp",
    "c++",
    "c",
}


def normalize_language(language: str | None) -> str:
    normalized = (language or "python").strip().lower()

    if normalized in {"py", "python3"}:
        return "python"

    if normalized in {"js", "node"}:
        return "javascript"

    if normalized in {"ts"}:
        return "typescript"

    if normalized in {"c++"}:
        return "cpp"

    return normalized


def run_code_against_tests(
    code: str,
    language: str | None,
    test_cases: list[dict[str, Any]],
    timeout_seconds: float = 2.5,
) -> dict[str, Any]:
    normalized_language = normalize_language(language)

    if normalized_language not in {
        "python",
        "javascript",
        "typescript",
        "java",
        "cpp",
        "c",
    }:
        return {
            "language": normalized_language,
            "passed": 0,
            "total": len(test_cases),
            "all_passed": False,
            "error": f"Running {language or 'this language'} is not supported yet.",
            "cases": [],
        }

    visible_tests = test_cases[:12] or [{"input": "", "expected": ""}]
    results = []

    with tempfile.TemporaryDirectory(prefix="azalea-code-") as temp_dir:
        temp_path = Path(temp_dir)
        file_path = temp_path / get_source_filename(normalized_language)
        file_path.write_text(
            build_runnable_source(code, normalized_language),
            encoding="utf-8",
        )

        compile_result = compile_if_needed(file_path, normalized_language)
        if compile_result:
            return {
                "language": normalized_language,
                "passed": 0,
                "total": len(visible_tests),
                "all_passed": False,
                "error": compile_result,
                "cases": [
                    {
                        "case_number": index + 1,
                        "input": str(test_case.get("input") or ""),
                        "expected": str(test_case.get("expected") or ""),
                        "actual": "",
                        "stderr": compile_result,
                        "passed": False,
                        "status": "compile_error",
                    }
                    for index, test_case in enumerate(visible_tests)
                ],
            }

        run_command = get_run_command(temp_path, file_path, normalized_language)
        if isinstance(run_command, str):
            return {
                "language": normalized_language,
                "passed": 0,
                "total": len(visible_tests),
                "all_passed": False,
                "error": run_command,
                "cases": [],
            }

        for index, test_case in enumerate(visible_tests):
            result = run_single_case(
                command=run_command,
                cwd=temp_path,
                language=normalized_language,
                test_input=str(test_case.get("input") or ""),
                expected=str(test_case.get("expected") or ""),
                timeout_seconds=timeout_seconds,
            )
            result["case_number"] = index + 1
            results.append(result)

    passed = sum(1 for result in results if result["passed"])

    return {
        "language": normalized_language,
        "passed": passed,
        "total": len(results),
        "all_passed": passed == len(results) and len(results) > 0,
        "error": None,
        "cases": results,
    }


def get_source_filename(language: str) -> str:
    return {
        "python": "solution.py",
        "javascript": "solution.js",
        "typescript": "solution.ts",
        "java": "Main.java",
        "cpp": "main.cpp",
        "c": "main.c",
    }[language]


def build_runnable_source(code: str, language: str) -> str:
    if language == "java" and "public class Main" not in code:
        return f"""{code}

public class Main {{
    public static void main(String[] args) throws Exception {{
        java.io.BufferedReader br = new java.io.BufferedReader(new java.io.InputStreamReader(System.in));
        StringBuilder input = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {{
            input.append(line).append("\\n");
        }}
        System.out.print(new Solution().solve(input.toString().trim()));
    }}
}}
"""

    if language == "cpp" and "int main" not in code:
        solution_call = get_cpp_solution_call(code)
        return f"""#include <bits/stdc++.h>
using namespace std;

{code}

int main() {{
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string input((istreambuf_iterator<char>(cin)), istreambuf_iterator<char>());
    Solution solution;
    cout << boolalpha << {solution_call};
    return 0;
}}
"""

    if language == "c" and "int main" not in code:
        return f"""{code}

int main(void) {{
    char input[8192];
    size_t length = fread(input, 1, sizeof(input) - 1, stdin);
    input[length] = '\\0';
    solve(input);
    return 0;
}}
"""

    if language == "typescript" and "readFileSync" not in code:
        return f"""{code}

import * as fs from "fs";
const input = fs.readFileSync(0, "utf8").trim();
console.log(solve(input));
"""

    if language == "javascript" and "readFileSync" not in code:
        return f"""{code}

const fs = require("fs");
const input = fs.readFileSync(0, "utf8").trim();
console.log(solve(input));
"""

    if language == "python" and "sys.stdin" not in code and "__main__" not in code:
        return f"""{code}

if __name__ == "__main__":
    import sys
    print(solve(sys.stdin.read().strip()))
"""

    return code


def get_cpp_solution_call(code: str) -> str:
    if re.search(r"\bsolve\s*\(", code):
        return "solution.solve(input)"

    method_match = re.search(
        r"\b(?:bool|int|long\s+long|string|double|float)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(?:const\s+)?(?:std::)?string\s*&?\s*[A-Za-z_][A-Za-z0-9_]*\s*\)",
        code,
    )

    if method_match:
        return f"solution.{method_match.group(1)}(input)"

    return "solution.solve(input)"


def compile_if_needed(file_path: Path, language: str) -> str | None:
    if language == "typescript":
        compiler = which("tsc.cmd") or which("tsc")
        if not compiler:
            return "TypeScript compiler is not available on the backend machine."
        completed = run_compile_command(
            [compiler, str(file_path), "--target", "ES2020", "--module", "commonjs"],
            cwd=file_path.parent,
            timeout=12,
        )
        emitted_js = file_path.with_suffix(".js")
        if completed["timed_out"]:
            return completed["stderr"]
        if completed["returncode"] != 0 and not emitted_js.exists():
            return completed["stderr"]
        return None

    if language == "java":
        compiler = which("javac")
        if not compiler:
            return "Java compiler is not available on the backend machine."
        completed = run_compile_command(
            [compiler, str(file_path)],
            cwd=file_path.parent,
            timeout=12,
        )
        return completed["stderr"] if completed["returncode"] != 0 else None

    if language == "cpp":
        compiler = which("g++")
        if not compiler:
            return "C++ compiler is not available on the backend machine."
        completed = run_compile_command(
            [compiler, str(file_path), "-std=c++17", "-O2", "-o", "main.exe"],
            cwd=file_path.parent,
            timeout=25,
        )
        return completed["stderr"] if completed["returncode"] != 0 else None

    if language == "c":
        compiler = which("gcc")
        if not compiler:
            return "C compiler is not available on the backend machine."
        completed = run_compile_command(
            [compiler, str(file_path), "-O2", "-o", "main.exe"],
            cwd=file_path.parent,
            timeout=25,
        )
        return completed["stderr"] if completed["returncode"] != 0 else None

    return None


def run_compile_command(
    command: list[str],
    cwd: Path,
    timeout: float,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
        stderr = "\n".join(
            part for part in [completed.stderr.strip(), completed.stdout.strip()] if part
        )
        return {
            "returncode": completed.returncode,
            "stderr": stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": 124,
            "stderr": f"Compilation timed out after {timeout:.0f}s.",
            "timed_out": True,
        }


def get_run_command(temp_path: Path, file_path: Path, language: str) -> list[str] | str:
    if language == "python":
        if not which("python"):
            return "Python is not available on the backend machine."
        return ["python", str(file_path)]

    if language == "javascript":
        if not which("node"):
            return "Node.js is not available on the backend machine."
        return ["node", str(file_path)]

    if language == "typescript":
        if not which("node"):
            return "Node.js is not available on the backend machine."
        return ["node", str(file_path.with_suffix(".js"))]

    if language == "java":
        if not which("java"):
            return "Java runtime is not available on the backend machine."
        return ["java", "-cp", str(temp_path), "Main"]

    if language in {"cpp", "c"}:
        executable = temp_path / "main.exe"
        return [str(executable)]

    return f"Running {language} is not supported yet."


def run_single_case(
    command: list[str],
    cwd: Path,
    language: str,
    test_input: str,
    expected: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            input=test_input,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(cwd),
        )
    except subprocess.TimeoutExpired:
        return {
            "input": test_input,
            "expected": expected,
            "actual": "",
            "stderr": f"Timed out after {timeout_seconds:.1f}s.",
            "passed": False,
            "status": "timeout",
        }
    except FileNotFoundError:
        return {
            "input": test_input,
            "expected": expected,
            "actual": "",
            "stderr": f"The {language} runtime is not available on the backend machine.",
            "passed": False,
            "status": "runtime_missing",
        }

    actual = completed.stdout.strip()
    expected_clean = expected.strip()
    stderr = completed.stderr.strip()
    passed = completed.returncode == 0 and actual == expected_clean

    return {
        "input": test_input,
        "expected": expected,
        "actual": actual,
        "stderr": stderr,
        "passed": passed,
        "status": "passed" if passed else "failed",
    }
