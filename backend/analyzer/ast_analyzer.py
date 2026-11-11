import ast
import json
import os


# ============================================================
# LOAD RULE CONFIGURATION
# ============================================================

def load_rule_config():

    # rules.json is located one folder above analyzer/
    rules_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "rules.json"
    )

    # If rules.json does not exist, enable all rules
    if not os.path.exists(rules_path):

        return {
            "enabled_rules": [
                "SEC001",
                "SEC002",
                "SEC003",
                "SEC004",
                "SEC005",
                "BUG001",
                "BUG002",
                "BUG003",
                "STYLE001",
                "STYLE002",
                "STYLE003",
                "PERF001",
                "PERF002"
            ],
            "ignored_rules": []
        }

    try:

        with open(
            rules_path,
            "r",
            encoding="utf-8"
        ) as file:

            config = json.load(file)

        return config

    except Exception:

        # If configuration has an error,
        # enable all rules instead of crashing backend

        return {
            "enabled_rules": [
                "SEC001",
                "SEC002",
                "SEC003",
                "SEC004",
                "SEC005",
                "BUG001",
                "BUG002",
                "BUG003",
                "STYLE001",
                "STYLE002",
                "STYLE003",
                "PERF001",
                "PERF002"
            ],
            "ignored_rules": []
        }


# ============================================================
# CODE ANALYZER
# ============================================================

class CodeAnalyzer(ast.NodeVisitor):

    def __init__(self):

        self.issues = []

        config = load_rule_config()

        self.enabled_rules = set(
            config.get("enabled_rules", [])
        )

        self.ignored_rules = set(
            config.get("ignored_rules", [])
        )

    # ============================================================
    # CHECK WHETHER RULE IS ENABLED
    # ============================================================

    def is_rule_enabled(self, rule_id):

        # Rule must be enabled
        if rule_id not in self.enabled_rules:
            return False

        # Ignored rules always have priority
        if rule_id in self.ignored_rules:
            return False

        return True

    # ============================================================
    # ADD ISSUE
    # ============================================================

    def add_issue(
        self,
        rule_id,
        category,
        severity,
        line,
        title,
        description,
        suggestion
    ):

        # Check rule configuration
        if not self.is_rule_enabled(rule_id):
            return

        self.issues.append({
            "rule_id": rule_id,
            "category": category,
            "severity": severity,
            "line": line,
            "title": title,
            "description": description,
            "suggestion": suggestion
        })

    # ============================================================
    # ASSIGNMENT RULES
    # SEC001 - HARDCODED CREDENTIAL
    # ============================================================

    def visit_Assign(self, node):

        for target in node.targets:

            if isinstance(target, ast.Name):

                variable_name = target.id.lower()

                sensitive_names = [
                    "password",
                    "passwd",
                    "secret",
                    "api_key",
                    "apikey",
                    "token",
                    "access_token",
                    "auth_token"
                ]

                if any(
                    name in variable_name
                    for name in sensitive_names
                ):

                    if isinstance(node.value, ast.Constant):

                        if isinstance(
                            node.value.value,
                            str
                        ):

                            self.add_issue(
                                rule_id="SEC001",
                                category="security",
                                severity="high",
                                line=node.lineno,
                                title="Possible hardcoded credential",
                                description=(
                                    "A sensitive value appears to be stored "
                                    "directly in the source code."
                                ),
                                suggestion=(
                                    "Move the secret to an environment "
                                    "variable or secure secret manager."
                                )
                            )

        self.generic_visit(node)

    # ============================================================
    # FUNCTION RULES
    # BUG002 - MUTABLE DEFAULT ARGUMENT
    # STYLE003 - LONG FUNCTION
    # ============================================================

    def visit_FunctionDef(self, node):

        # --------------------------------------------------------
        # BUG002 - Mutable default argument
        # --------------------------------------------------------

        for default in node.args.defaults:

            if isinstance(
                default,
                (
                    ast.List,
                    ast.Dict,
                    ast.Set
                )
            ):

                self.add_issue(
                    rule_id="BUG002",
                    category="bug",
                    severity="medium",
                    line=node.lineno,
                    title="Mutable default argument",
                    description=(
                        "Using a list, dictionary, or set as a default "
                        "function argument can cause values to persist "
                        "between function calls."
                    ),
                    suggestion=(
                        "Use None as the default value and create the "
                        "mutable object inside the function."
                    )
                )

        # --------------------------------------------------------
        # STYLE003 - Long function
        # --------------------------------------------------------

        if node.end_lineno:

            function_length = (
                node.end_lineno -
                node.lineno +
                1
            )

            if function_length > 50:

                self.add_issue(
                    rule_id="STYLE003",
                    category="style",
                    severity="medium",
                    line=node.lineno,
                    title="Function is too long",
                    description=(
                        f"This function contains approximately "
                        f"{function_length} lines of code."
                    ),
                    suggestion=(
                        "Break the function into smaller functions "
                        "with clear responsibilities."
                    )
                )

        self.generic_visit(node)

    # ============================================================
    # CALL RULES
    # SEC002 - EVAL
    # SEC003 - EXEC
    # SEC004 - OS.SYSTEM
    # SEC005 - SUBPROCESS
    # PERF002 - LIST(RANGE())
    # ============================================================

    def visit_Call(self, node):

        # --------------------------------------------------------
        # SEC002 - eval()
        # --------------------------------------------------------

        if isinstance(node.func, ast.Name):

            if node.func.id == "eval":

                self.add_issue(
                    rule_id="SEC002",
                    category="security",
                    severity="critical",
                    line=node.lineno,
                    title="Dangerous use of eval()",
                    description=(
                        "eval() can execute dynamically supplied Python "
                        "code and may allow arbitrary code execution."
                    ),
                    suggestion=(
                        "Avoid eval(). Use safer alternatives such as "
                        "literal_eval() when appropriate."
                    )
                )

        # --------------------------------------------------------
        # SEC003 - exec()
        # --------------------------------------------------------

        if isinstance(node.func, ast.Name):

            if node.func.id == "exec":

                self.add_issue(
                    rule_id="SEC003",
                    category="security",
                    severity="critical",
                    line=node.lineno,
                    title="Dangerous use of exec()",
                    description=(
                        "exec() can execute dynamically supplied Python "
                        "code and may allow arbitrary code execution."
                    ),
                    suggestion=(
                        "Avoid exec(). Replace dynamic code execution "
                        "with safer and controlled logic."
                    )
                )

        # --------------------------------------------------------
        # Attribute based calls
        # --------------------------------------------------------

        if isinstance(node.func, ast.Attribute):

            # ----------------------------------------------------
            # SEC004 - os.system()
            # ----------------------------------------------------

            if (
                isinstance(
                    node.func.value,
                    ast.Name
                )
                and node.func.value.id == "os"
                and node.func.attr == "system"
            ):

                self.add_issue(
                    rule_id="SEC004",
                    category="security",
                    severity="high",
                    line=node.lineno,
                    title="Potentially dangerous system command",
                    description=(
                        "os.system() executes an operating-system command "
                        "and may be unsafe when input is user controlled."
                    ),
                    suggestion=(
                        "Avoid os.system() when possible. Use safer "
                        "subprocess APIs with controlled arguments."
                    )
                )

            # ----------------------------------------------------
            # SEC005 - subprocess
            # ----------------------------------------------------

            if (
                isinstance(
                    node.func.value,
                    ast.Name
                )
                and node.func.value.id == "subprocess"
                and node.func.attr in [
                    "call",
                    "run",
                    "Popen"
                ]
            ):

                self.add_issue(
                    rule_id="SEC005",
                    category="security",
                    severity="high",
                    line=node.lineno,
                    title="Potentially unsafe subprocess usage",
                    description=(
                        "Subprocess execution can become dangerous when "
                        "commands or arguments contain untrusted input."
                    ),
                    suggestion=(
                        "Use controlled argument lists and avoid "
                        "shell=True with untrusted input."
                    )
                )

        # --------------------------------------------------------
        # PERF002 - list(range())
        # --------------------------------------------------------

        if isinstance(node.func, ast.Name):

            if node.func.id == "list":

                if len(node.args) == 1:

                    argument = node.args[0]

                    if (
                        isinstance(
                            argument,
                            ast.Call
                        )
                        and isinstance(
                            argument.func,
                            ast.Name
                        )
                        and argument.func.id == "range"
                    ):

                        self.add_issue(
                            rule_id="PERF002",
                            category="performance",
                            severity="low",
                            line=node.lineno,
                            title="Unnecessary list creation",
                            description=(
                                "Creating a list from range() may use "
                                "additional memory when iteration is enough."
                            ),
                            suggestion=(
                                "Iterate over range() directly when "
                                "you do not need a list."
                            )
                        )

        self.generic_visit(node)

    # ============================================================
    # BUG001 - NONE COMPARISON
    # ============================================================

    def visit_Compare(self, node):

        for operator in node.ops:

            if isinstance(
                operator,
                (
                    ast.Eq,
                    ast.NotEq
                )
            ):

                for comparator in node.comparators:

                    if isinstance(
                        comparator,
                        ast.Constant
                    ):

                        if comparator.value is None:

                            if isinstance(
                                operator,
                                ast.Eq
                            ):

                                self.add_issue(
                                    rule_id="BUG001",
                                    category="bug",
                                    severity="medium",
                                    line=node.lineno,
                                    title=(
                                        "Use 'is None' instead of "
                                        "'== None'"
                                    ),
                                    description=(
                                        "None comparisons should normally "
                                        "use identity comparison."
                                    ),
                                    suggestion=(
                                        "Replace '== None' with "
                                        "'is None'."
                                    )
                                )

                            else:

                                self.add_issue(
                                    rule_id="BUG001",
                                    category="bug",
                                    severity="medium",
                                    line=node.lineno,
                                    title=(
                                        "Use 'is not None' instead of "
                                        "'!= None'"
                                    ),
                                    description=(
                                        "None comparisons should normally "
                                        "use identity comparison."
                                    ),
                                    suggestion=(
                                        "Replace '!= None' with "
                                        "'is not None'."
                                    )
                                )

        self.generic_visit(node)

    # ============================================================
    # BUG003 - BARE EXCEPT
    # ============================================================

    def visit_ExceptHandler(self, node):

        if node.type is None:

            self.add_issue(
                rule_id="BUG003",
                category="bug",
                severity="medium",
                line=node.lineno,
                title="Bare except detected",
                description=(
                    "A bare except catches every exception, including "
                    "unexpected system exceptions."
                ),
                suggestion=(
                    "Catch a specific exception type instead of using "
                    "a bare except."
                )
            )

        self.generic_visit(node)

    # ============================================================
    # STYLE001 - UNCLEAR VARIABLE NAME
    # ============================================================

    def visit_Name(self, node):

        if isinstance(
            node.ctx,
            ast.Store
        ):

            variable_name = node.id

            bad_names = [
                "x",
                "y",
                "z",
                "a",
                "b",
                "c",
                "tmp",
                "temp",
                "foo",
                "bar"
            ]

            if variable_name in bad_names:

                self.add_issue(
                    rule_id="STYLE001",
                    category="style",
                    severity="low",
                    line=node.lineno,
                    title="Unclear variable name",
                    description=(
                        f"The variable name '{variable_name}' does not "
                        "clearly describe the data it stores."
                    ),
                    suggestion=(
                        "Use a descriptive variable name that explains "
                        "the purpose of the value."
                    )
                )

        self.generic_visit(node)

    # ============================================================
    # STYLE002 - DEEP NESTING
    # ============================================================

    def calculate_nesting(
        self,
        node,
        depth=0
    ):

        maximum_depth = depth

        for child in ast.iter_child_nodes(node):

            additional_depth = 0

            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.Try,
                    ast.With
                )
            ):

                additional_depth = 1

            child_depth = self.calculate_nesting(
                child,
                depth + additional_depth
            )

            maximum_depth = max(
                maximum_depth,
                child_depth
            )

        return maximum_depth

    def visit_If(self, node):

        nesting_depth = self.calculate_nesting(node)

        if nesting_depth >= 4:

            self.add_issue(
                rule_id="STYLE002",
                category="style",
                severity="medium",
                line=node.lineno,
                title="Deeply nested code",
                description=(
                    "This code contains several levels of nested "
                    "conditions or loops, which can reduce readability."
                ),
                suggestion=(
                    "Consider extracting logic into smaller functions "
                    "or using early returns."
                )
            )

        self.generic_visit(node)

    # ============================================================
    # PERF001 - LOOP WITH APPEND
    # ============================================================

    def visit_For(self, node):

        found_append = False

        for child in ast.walk(node):

            if isinstance(
                child,
                ast.Call
            ):

                if isinstance(
                    child.func,
                    ast.Attribute
                ):

                    if child.func.attr == "append":

                        found_append = True
                        break

        if found_append:

            self.add_issue(
                rule_id="PERF001",
                category="performance",
                severity="low",
                line=node.lineno,
                title="Possible inefficient loop",
                description=(
                    "A loop is repeatedly appending values to a list. "
                    "A list comprehension may be simpler and faster "
                    "for simple operations."
                ),
                suggestion=(
                    "Consider using a list comprehension when the "
                    "operation is simple."
                )
            )

        self.generic_visit(node)


# ============================================================
# MAIN ANALYZER FUNCTION
# ============================================================

def analyze_python_code(code: str):

    try:

        tree = ast.parse(code)

    except SyntaxError as error:

        config = load_rule_config()

        enabled_rules = set(
            config.get("enabled_rules", [])
        )

        ignored_rules = set(
            config.get("ignored_rules", [])
        )

        # Only return syntax issue when SYNTAX001 is enabled
        if (
            "SYNTAX001" in enabled_rules
            and "SYNTAX001" not in ignored_rules
        ):

            return [
                {
                    "rule_id": "SYNTAX001",
                    "category": "bug",
                    "severity": "critical",
                    "line": error.lineno or 1,
                    "title": "Python syntax error",
                    "description": str(error.msg),
                    "suggestion": (
                        "Fix the syntax error before reviewing the code."
                    )
                }
            ]

        return []

    analyzer = CodeAnalyzer()

    analyzer.visit(tree)

    return analyzer.issues

