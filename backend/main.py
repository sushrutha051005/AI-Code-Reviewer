from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ast
import re

from analyzer.ast_analyzer import analyze_python_code
from analyzer.llm_reviewer import review_code_with_llm
from analyzer.git_diff_analyzer import analyze_git_diff


app = FastAPI(
    title="AI Code Reviewer",
    description="AI-powered Python code review using Static Analysis and Ollama",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


class ReviewRequest(BaseModel):
    language: str = "python"
    code: str


class DiffRequest(BaseModel):
    diff: str


# =========================================================
# PYTHON CODE VALIDATION
# =========================================================

def is_related_python_code(code: str) -> bool:

    if not code:
        return False

    code = code.strip()

    if not code:
        return False

    # -----------------------------------------------------
    # Reject obvious normal text / shopping lists
    # -----------------------------------------------------

    lines = [
        line.strip()
        for line in code.splitlines()
        if line.strip()
    ]

    if not lines:
        return False

    # -----------------------------------------------------
    # Strong Python indicators
    # -----------------------------------------------------

    strong_python_patterns = [
        r"^\s*def\s+\w+\s*\(",
        r"^\s*class\s+\w+",
        r"^\s*import\s+\w+",
        r"^\s*from\s+\w+",
        r"^\s*if\s+.+:",
        r"^\s*elif\s+.+:",
        r"^\s*else\s*:",
        r"^\s*for\s+.+\s+in\s+.+:",
        r"^\s*while\s+.+:",
        r"^\s*try\s*:",
        r"^\s*except\b",
        r"^\s*finally\s*:",
        r"^\s*with\s+.+:",
        r"^\s*return\b",
        r"^\s*raise\b",
        r"^\s*yield\b",
        r"^\s*async\s+def\b",
        r"^\s*await\b",
        r"^\s*print\s*\(",
        r"^\s*assert\b",
        r"^\s*lambda\b",
        r"^\s*@\w+"
    ]

    strong_match = False

    for line in lines:
        for pattern in strong_python_patterns:
            if re.search(pattern, line):
                strong_match = True
                break

        if strong_match:
            break

    # -----------------------------------------------------
    # Python syntax structures
    # -----------------------------------------------------

    syntax_score = 0

    for line in lines:

        stripped = line.strip()

        if re.match(r"^\w+\s*=\s*.+", stripped):
            syntax_score += 1

        if "==" in stripped:
            syntax_score += 1

        if "!=" in stripped:
            syntax_score += 1

        if "+=" in stripped:
            syntax_score += 1

        if "-=" in stripped:
            syntax_score += 1

        if "*=" in stripped:
            syntax_score += 1

        if "/=" in stripped:
            syntax_score += 1

        if "(" in stripped and ")" in stripped:
            syntax_score += 1

        if ":" in stripped:
            syntax_score += 1

        if "[" in stripped and "]" in stripped:
            syntax_score += 1

        if "{" in stripped and "}" in stripped:
            syntax_score += 1

    # -----------------------------------------------------
    # First try Python AST
    # -----------------------------------------------------

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    if not tree.body:
        return False

    # -----------------------------------------------------
    # AST nodes
    # -----------------------------------------------------

    python_nodes = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Import,
        ast.ImportFrom,
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Return,
        ast.Raise,
        ast.Assert,
        ast.Call,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp
    )

    has_python_ast = False

    for node in ast.walk(tree):
        if isinstance(node, python_nodes):
            has_python_ast = True
            break

    if not has_python_ast:
        return False

    # -----------------------------------------------------
    # VERY IMPORTANT:
    #
    # Simple random English text can sometimes be valid
    # Python expressions. We therefore require stronger
    # evidence for multi-line natural-language content.
    # -----------------------------------------------------

    natural_language_words = {
        "the",
        "this",
        "that",
        "these",
        "those",
        "please",
        "list",
        "shopping",
        "grocery",
        "milk",
        "bread",
        "rice",
        "sugar",
        "apples",
        "bananas",
        "tomatoes",
        "potatoes",
        "oil",
        "biscuits",
        "tea",
        "powder",
        "welcome",
        "hello",
        "today",
        "weather",
        "meeting",
        "school",
        "college",
        "student",
        "project",
        "report"
    }

    lowercase_words = set(
        re.findall(
            r"\b[a-zA-Z]+\b",
            code.lower()
        )
    )

    natural_language_count = len(
        lowercase_words.intersection(
            natural_language_words
        )
    )

    # -----------------------------------------------------
    # If there are strong Python structures, accept
    # -----------------------------------------------------

    if strong_match:
        return True

    # -----------------------------------------------------
    # Assignment / syntax based Python
    # -----------------------------------------------------

    if syntax_score >= 2:
        return True

    # -----------------------------------------------------
    # If content looks like natural language and there
    # is no strong Python indicator, reject it.
    # -----------------------------------------------------

    if natural_language_count >= 2:
        return False

    # -----------------------------------------------------
    # Single simple Python statement
    #
    # Examples:
    #
    # x = 10
    # name = "Sai"
    # print("Hello")
    # -----------------------------------------------------

    if len(lines) <= 3 and syntax_score >= 1:
        return True

    return False


# =========================================================
# SEVERITY COUNT
# =========================================================

def count_severities(issues):

    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0
    }

    for issue in issues:

        severity = str(
            issue.get("severity", "medium")
        ).lower()

        if severity in counts:
            counts[severity] += 1
        else:
            counts["medium"] += 1

    return counts


# =========================================================
# NORMAL REVIEW RESULT
# =========================================================

def create_review_result(
    language,
    code,
    static_issues,
    llm_result,
    source="Code Editor"
):

    llm_issues = []

    if isinstance(llm_result, dict):

        possible_issues = llm_result.get(
            "issues",
            []
        )

        if isinstance(possible_issues, list):
            llm_issues = possible_issues

    combined = []

    for issue in static_issues:

        issue = dict(issue)

        issue.setdefault(
            "detected_by",
            "Static Analysis"
        )

        combined.append(issue)

    for issue in llm_issues:

        issue = dict(issue)

        issue.setdefault(
            "detected_by",
            "AI / Ollama"
        )

        combined.append(issue)

    counts = count_severities(combined)

    return {
        "status": "success",
        "related": True,

        "source": source,

        "language": language,

        "code": code,

        "summary": {
            "total": len(combined),
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
            "info": counts["info"]
        },

        "total_issues": len(combined),

        "static_analysis": {
            "status": "completed",
            "total_issues": len(static_issues),
            "issues": static_issues
        },

        "llm_analysis": {
            "status": (
                llm_result.get(
                    "status",
                    "unknown"
                )
                if isinstance(llm_result, dict)
                else "unknown"
            ),

            "message": (
                llm_result.get(
                    "message",
                    ""
                )
                if isinstance(llm_result, dict)
                else ""
            ),

            "model": (
                llm_result.get(
                    "model",
                    "llama3.2:latest"
                )
                if isinstance(llm_result, dict)
                else "llama3.2:latest"
            ),

            "total_issues": len(llm_issues),

            "issues": llm_issues
        },

        "issues": combined
    }


# =========================================================
# UNRELATED RESULT
# =========================================================

def create_unrelated_result(
    message,
    source="Code Editor"
):

    return {

        # IMPORTANT
        "status": "unrelated",

        # IMPORTANT
        "related": False,

        "source": source,

        "message": message,

        "language": "python",

        "code": "",

        "summary": {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        },

        "total_issues": 0,

        "static_analysis": {
            "status": "not_analyzed",
            "total_issues": 0,
            "issues": []
        },

        "llm_analysis": {
            "status": "not_analyzed",
            "total_issues": 0,
            "issues": []
        },

        "issues": []
    }


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "status": "running",
        "message": "AI Code Reviewer",
        "model": "Rule Based + AI"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "AI Code Reviewer"
    }


# =========================================================
# REVIEW CODE
# =========================================================

@app.post("/review")
def review_code(request: ReviewRequest):

    language = request.language.lower().strip()

    code = request.code or ""

    # -----------------------------------------------------
    # ONLY PYTHON SUPPORTED
    # -----------------------------------------------------

    if language != "python":

        return create_unrelated_result(
            message=(
                "This content is not related to "
                "Python source code. Please enter "
                "valid Python code to analyze."
            ),
            source="Code Editor"
        )

    # -----------------------------------------------------
    # EMPTY CODE
    # -----------------------------------------------------

    if not code.strip():

        return create_unrelated_result(
            message=(
                "No Python code was provided. "
                "Please enter valid Python code to analyze."
            ),
            source="Code Editor"
        )

    # -----------------------------------------------------
    # CHECK WHETHER IT IS REALLY PYTHON
    # -----------------------------------------------------

    if not is_related_python_code(code):

        return create_unrelated_result(
            message=(
                "This content is not related to "
                "Python source code. Please enter "
                "valid Python code to analyze."
            ),
            source="Code Editor"
        )

    # -----------------------------------------------------
    # STATIC ANALYSIS
    # -----------------------------------------------------

    try:

        static_issues = analyze_python_code(
            code
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Static analysis failed: {str(exc)}"
            )
        )

    # -----------------------------------------------------
    # AI ANALYSIS
    # -----------------------------------------------------

    try:

        llm_result = review_code_with_llm(
            code,
            language
        )

    except Exception:

        llm_result = {
            "status": "unavailable",

            "message": (
                "AI review is unavailable. "
                "Static analysis results are shown."
            ),

            "model": "llama3.2:latest",

            "issues": []
        }

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    return create_review_result(

        language=language,

        code=code,

        static_issues=static_issues,

        llm_result=llm_result,

        source="Code Editor"
    )


# =========================================================
# REVIEW PYTHON FILE
# =========================================================

@app.post("/review-file")
async def review_file(
    file: UploadFile = File(...)
):

    filename = file.filename or ""

    if not filename.lower().endswith(".py"):

        return create_unrelated_result(
            message=(
                "This file is not related to "
                "Python source code. Please upload "
                "a valid Python (.py) file."
            ),
            source="Python File"
        )

    try:

        content = await file.read()

        code = content.decode(
            "utf-8"
        )

    except UnicodeDecodeError:

        return create_unrelated_result(
            message=(
                "This file does not contain valid "
                "Python source code."
            ),
            source="Python File"
        )

    if not is_related_python_code(code):

        return create_unrelated_result(
            message=(
                "This file does not contain valid "
                "Python source code. Please upload "
                "a valid Python file."
            ),
            source="Python File"
        )

    try:

        static_issues = analyze_python_code(
            code
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Static analysis failed: {str(exc)}"
            )
        )

    try:

        llm_result = review_code_with_llm(
            code,
            "python"
        )

    except Exception:

        llm_result = {
            "status": "unavailable",

            "message": (
                "AI review is unavailable. "
                "Static analysis results are shown."
            ),

            "model": "llama3.2:latest",

            "issues": []
        }

    return create_review_result(

        language="python",

        code=code,

        static_issues=static_issues,

        llm_result=llm_result,

        source="Python File"
    )


# =========================================================
# REVIEW GIT DIFF
# =========================================================

@app.post("/review-diff")
def review_diff(request: DiffRequest):

    if not request.diff.strip():

        raise HTTPException(
            status_code=400,
            detail="Please provide a Git diff."
        )

    try:

        return analyze_git_diff(
            request.diff
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Git diff analysis failed: {str(exc)}"
            )
        )