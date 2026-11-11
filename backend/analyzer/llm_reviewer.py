import json
import re
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:latest"
OLLAMA_TIMEOUT = 120


def clean_json_response(raw_response):
    """
    Clean Ollama output and extract a JSON object.
    Handles:
    - normal JSON
    - ```json ... ```
    - extra text before/after JSON
    """

    if not raw_response:
        return None

    text = raw_response.strip()

    # Remove markdown code fences
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    # First attempt: complete response is JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object inside extra text
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        possible_json = text[start:end + 1]

        try:
            return json.loads(possible_json)
        except json.JSONDecodeError:
            pass

    return None


def review_code_with_llm(code, language="python"):
    """
    Review source code using Ollama local LLM.
    """

    prompt = f"""
You are an expert software security and code reviewer.

Review the following {language} source code.

Find important:
- Security vulnerabilities
- Bugs
- Unsafe functions
- Bad programming practices
- Performance problems
- Reliability problems

IMPORTANT:
Return ONLY valid JSON.
Do not return Markdown.
Do not use ```json.
Do not write explanations outside JSON.

Use exactly this JSON structure:

{{
  "issues": [
    {{
      "severity": "critical",
      "category": "security",
      "title": "Short issue title",
      "line": 1,
      "description": "Explain the problem clearly.",
      "suggested_fix": "Explain how to fix it."
    }}
  ]
}}

Severity must be exactly one of:
critical
high
medium
low

Category must be one of:
security
bug
style
performance
reliability

If there are no important issues, return:

{{
  "issues": []
}}

SOURCE CODE:

{code}
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 800
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        raw_response = data.get("response", "")

        parsed = clean_json_response(raw_response)

        # If JSON parsing fails, try once again without format=json
        if parsed is None:

            fallback_payload = {
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 800
                }
            }

            fallback_response = requests.post(
                OLLAMA_URL,
                json=fallback_payload,
                timeout=OLLAMA_TIMEOUT
            )

            fallback_response.raise_for_status()

            fallback_data = fallback_response.json()

            raw_response = fallback_data.get("response", "")

            parsed = clean_json_response(raw_response)

        if parsed is None:
            return {
                "status": "error",
                "message": "Ollama returned a response that could not be parsed as JSON.",
                "model": MODEL_NAME,
                "total_issues": 0,
                "issues": []
            }

        if not isinstance(parsed, dict):
            return {
                "status": "error",
                "message": "Ollama returned invalid JSON structure.",
                "model": MODEL_NAME,
                "total_issues": 0,
                "issues": []
            }

        issues = parsed.get("issues", [])

        if not isinstance(issues, list):
            issues = []

        valid_severities = {
            "critical",
            "high",
            "medium",
            "low"
        }

        valid_categories = {
            "security",
            "bug",
            "style",
            "performance",
            "reliability"
        }

        cleaned_issues = []

        for issue in issues:

            if not isinstance(issue, dict):
                continue

            severity = str(
                issue.get("severity", "medium")
            ).lower().strip()

            category = str(
                issue.get("category", "bug")
            ).lower().strip()

            title = str(
                issue.get("title", "AI detected issue")
            ).strip()

            description = str(
                issue.get("description", "")
            ).strip()

            suggested_fix = str(
                issue.get("suggested_fix", "")
            ).strip()

            if severity not in valid_severities:
                severity = "medium"

            if category not in valid_categories:
                category = "bug"

            try:
                line = int(issue.get("line", 1))
            except (ValueError, TypeError):
                line = 1

            if line < 1:
                line = 1

            if not description:
                description = "Potential issue detected by the local AI reviewer."

            if not suggested_fix:
                suggested_fix = "Review and correct the identified issue."

            cleaned_issues.append(
                {
                    "severity": severity,
                    "category": category,
                    "title": title,
                    "line": line,
                    "description": description,
                    "suggested_fix": suggested_fix,
                    "detected_by": "AI / Ollama"
                }
            )

        # Remove duplicate AI findings
        unique_issues = []
        seen = set()

        for issue in cleaned_issues:

            key = (
                issue["line"],
                issue["category"],
                issue["title"].lower()
            )

            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return {
            "status": "success",
            "message": "AI review completed successfully.",
            "model": MODEL_NAME,
            "total_issues": len(unique_issues),
            "issues": unique_issues
        }

    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "message": "Could not connect to Ollama. Make sure Ollama is running.",
            "model": MODEL_NAME,
            "total_issues": 0,
            "issues": []
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Ollama request timed out.",
            "model": MODEL_NAME,
            "total_issues": 0,
            "issues": []
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Ollama request failed: {str(e)}",
            "model": MODEL_NAME,
            "total_issues": 0,
            "issues": []
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"AI review failed: {str(e)}",
            "model": MODEL_NAME,
            "total_issues": 0,
            "issues": []
        }