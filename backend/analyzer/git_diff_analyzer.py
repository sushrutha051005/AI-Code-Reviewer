import re


def analyze_git_diff(diff: str):
    """
    Analyze added lines from a Git diff.
    """

    if not diff or not diff.strip():
        return {
            "status": "error",
            "message": "Please provide a Git diff.",
            "total_issues": 0,
            "issues": []
        }

    issues = []
    current_line = 1

    for line in diff.splitlines():

        # Track added lines only.
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)

            if match:
                current_line = int(match.group(1))

            continue

        if line.startswith("+") and not line.startswith("+++"):
            added_code = line[1:].strip()
            lowered = added_code.lower()

            # Hardcoded password detection
            if (
                "password" in lowered
                and "=" in added_code
                and (
                    '"' in added_code
                    or "'" in added_code
                )
            ):
                issues.append({
                    "rule_id": "DIFF001",
                    "category": "security",
                    "severity": "high",
                    "line": current_line,
                    "title": "Hardcoded password",
                    "description": (
                        "A password appears to be directly "
                        "stored in the source code."
                    ),
                    "suggestion": (
                        "Use environment variables or a secure "
                        "secret-management system."
                    ),
                    "detected_by": "Git Diff Analysis"
                })

            # eval detection
            if "eval(" in lowered:
                issues.append({
                    "rule_id": "DIFF002",
                    "category": "security",
                    "severity": "critical",
                    "line": current_line,
                    "title": "Unsafe eval usage",
                    "description": (
                        "eval() can execute arbitrary code and "
                        "may create a code-injection vulnerability."
                    ),
                    "suggestion": (
                        "Avoid eval(). Use safe parsing or explicitly "
                        "validated input instead."
                    ),
                    "detected_by": "Git Diff Analysis"
                })

            # exec detection
            if "exec(" in lowered:
                issues.append({
                    "rule_id": "DIFF003",
                    "category": "security",
                    "severity": "critical",
                    "line": current_line,
                    "title": "Unsafe exec usage",
                    "description": (
                        "exec() executes dynamically supplied code "
                        "and can create a serious security risk."
                    ),
                    "suggestion": (
                        "Avoid exec() and use safe, predefined "
                        "operations instead."
                    ),
                    "detected_by": "Git Diff Analysis"
                })

            # SQL injection style detection
            if (
                "execute(" in lowered
                and (
                    "+" in added_code
                    or "%" in added_code
                    or "f\"" in added_code
                    or "f'" in added_code
                )
            ):
                issues.append({
                    "rule_id": "DIFF004",
                    "category": "security",
                    "severity": "high",
                    "line": current_line,
                    "title": "Possible SQL injection",
                    "description": (
                        "SQL query construction appears to use "
                        "string interpolation or concatenation."
                    ),
                    "suggestion": (
                        "Use parameterized queries instead of "
                        "building SQL strings directly."
                    ),
                    "detected_by": "Git Diff Analysis"
                })

            current_line += 1

        elif not line.startswith("-"):
            current_line += 1

    return {
        "status": "success",
        "message": "Git diff analysis completed successfully.",
        "total_issues": len(issues),
        "issues": issues
    }