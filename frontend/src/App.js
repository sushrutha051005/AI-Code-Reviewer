import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [page, setPage] = useState("home");
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [file, setFile] = useState(null);
  const [diff, setDiff] = useState("");

  // =========================================================
  // LOAD HISTORY
  // =========================================================

  useEffect(() => {
    const savedHistory = localStorage.getItem(
      "aiCodeReviewerHistory"
    );

    if (savedHistory) {
      try {
        setHistory(JSON.parse(savedHistory));
      } catch {
        setHistory([]);
      }
    }
  }, []);

  // =========================================================
  // SAVE HISTORY
  // =========================================================

  const saveToHistory = (reviewResult) => {
    if (
      !reviewResult ||
      reviewResult.status !== "success" ||
      reviewResult.related === false
    ) {
      return;
    }

    const item = {
      id: Date.now(),

      date: new Date().toLocaleString(),

      language:
        reviewResult.language || "python",

      source:
        reviewResult.source || "Code Editor",

      totalIssues:
        reviewResult.summary?.total ??
        reviewResult.total_issues ??
        0,

      critical:
        reviewResult.summary?.critical ?? 0,

      high:
        reviewResult.summary?.high ?? 0,

      medium:
        reviewResult.summary?.medium ?? 0,

      low:
        reviewResult.summary?.low ?? 0,

      code:
        reviewResult.code || "",

      result: reviewResult
    };

    setHistory((previous) => {
      const updated = [
        item,
        ...previous
      ].slice(0, 20);

      localStorage.setItem(
        "aiCodeReviewerHistory",
        JSON.stringify(updated)
      );

      return updated;
    });
  };

  // =========================================================
  // NEW REVIEW
  // =========================================================

  const newReview = () => {
    setCode("");
    setLanguage("python");
    setResult(null);
    setError("");
    setFile(null);
    setDiff("");
    setPage("analyze");
  };

  // =========================================================
  // ANALYZE CODE
  // =========================================================

  const analyzeCode = async () => {
    if (!code.trim()) {
      setError(
        "Please enter Python code to analyze."
      );
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_URL}/review`,
        {
          language: language,
          code: code
        },
        {
          timeout: 120000
        }
      );

      const reviewResult = response.data;

      console.log(
        "BACKEND REVIEW RESULT:",
        reviewResult
      );

      // -------------------------------------------------------
      // UNRELATED CONTENT
      // -------------------------------------------------------

      if (
        reviewResult &&
        (
          reviewResult.status === "unrelated" ||
          reviewResult.related === false
        )
      ) {
        if (!reviewResult.code) {
          reviewResult.code = code;
        }

        setResult(reviewResult);
        setError("");
        setPage("results");
        return;
      }

      // -------------------------------------------------------
      // INVALID BACKEND RESPONSE
      // -------------------------------------------------------

      if (
        !reviewResult ||
        reviewResult.status !== "success" ||
        reviewResult.related !== true
      ) {
        setResult({
          status: "unrelated",

          related: false,

          source: "Code Editor",

          language: language,

          code: code,

          message:
            "This content is not related to Python source code. Please enter valid Python code to analyze.",

          summary: {
            total: 0,
            critical: 0,
            high: 0,
            medium: 0,
            low: 0,
            info: 0
          },

          total_issues: 0,

          static_analysis: {
            status: "not_analyzed",
            total_issues: 0,
            issues: []
          },

          llm_analysis: {
            status: "not_analyzed",
            total_issues: 0,
            issues: []
          },

          issues: []
        });

        setError("");
        setPage("results");
        return;
      }

      // -------------------------------------------------------
      // SUCCESS
      // -------------------------------------------------------

      setResult(reviewResult);
      setError("");
      setPage("results");

      saveToHistory(reviewResult);

    } catch (err) {
      console.error(
        "Code review error:",
        err
      );

      if (err.response?.data?.detail) {
        setError(
          err.response.data.detail
        );
      } else {
        setError(
          "Unable to connect to the AI Code Reviewer backend."
        );
      }

    } finally {
      setLoading(false);
    }
  };

  // =========================================================
  // ANALYZE PYTHON FILE
  // =========================================================

  const analyzeFile = async () => {
    if (!file) {
      setError(
        "Please select a Python (.py) file."
      );
      return;
    }

    if (!file.name.toLowerCase().endsWith(".py")) {
      setError(
        "Only Python (.py) files are supported."
      );
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file
      );

      const response = await axios.post(
        `${API_URL}/review-file`,
        formData,
        {
          headers: {
            "Content-Type":
              "multipart/form-data"
          },

          timeout: 120000
        }
      );

      const reviewResult = response.data;

      // Read file text so unrelated content
      // can still be displayed on Results page.
      let fileContent = "";

      try {
        fileContent = await file.text();
      } catch {
        fileContent = "";
      }

      if (
        reviewResult &&
        (
          reviewResult.status === "unrelated" ||
          reviewResult.related === false
        )
      ) {
        if (!reviewResult.code) {
          reviewResult.code = fileContent;
        }

        setResult(reviewResult);
        setError("");
        setPage("results");
        return;
      }

      if (
        reviewResult &&
        !reviewResult.code &&
        fileContent
      ) {
        reviewResult.code = fileContent;
      }

      setResult(reviewResult);
      setError("");
      setPage("results");

      if (
        reviewResult &&
        reviewResult.status === "success" &&
        reviewResult.related === true
      ) {
        saveToHistory(reviewResult);
      }

    } catch (err) {
      console.error(
        "File review error:",
        err
      );

      if (err.response?.data?.detail) {
        setError(
          err.response.data.detail
        );
      } else {
        setError(
          "Unable to analyze the uploaded file."
        );
      }

    } finally {
      setLoading(false);
    }
  };

  // =========================================================
  // ANALYZE GIT DIFF
  // =========================================================

  const analyzeDiff = async () => {
    if (!diff.trim()) {
      setError(
        "Please paste a Git diff."
      );
      return;
    }

    const isGitDiff =
      diff.includes("@@") ||
      diff.includes("diff --git") ||
      diff.includes("--- a/") ||
      diff.includes("+++ b/") ||
      /^\s*[+-][^+-]/m.test(diff);

    // -------------------------------------------------------
    // INVALID DIFF
    // -------------------------------------------------------

    if (!isGitDiff) {
      setResult({
        status: "unrelated",

        related: false,

        source: "Git Diff",

        language: "python",

        code: diff,

        message:
          "This content is not a Git diff or Python source code. Please paste a valid Git diff to analyze.",

        summary: {
          total: 0,
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
          info: 0
        },

        total_issues: 0,

        static_analysis: {
          status: "not_analyzed",
          total_issues: 0,
          issues: []
        },

        llm_analysis: {
          status: "not_analyzed",
          total_issues: 0,
          issues: []
        },

        issues: []
      });

      setError("");
      setPage("results");

      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_URL}/review-diff`,
        {
          diff: diff
        },
        {
          timeout: 120000
        }
      );

      const diffResult = response.data;

      const issues = Array.isArray(
        diffResult.issues
      )
        ? diffResult.issues
        : [];

      const severityCounts = {
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        info: 0
      };

      issues.forEach((issue) => {
        const severity = String(
          issue.severity || "medium"
        ).toLowerCase();

        if (
          severityCounts[severity] !==
          undefined
        ) {
          severityCounts[severity]++;
        }
      });

      const convertedResult = {
        status: "success",

        related: true,

        source: "Git Diff",

        language: "python",

        code: diff,

        summary: {
          total: issues.length,

          critical:
            severityCounts.critical,

          high:
            severityCounts.high,

          medium:
            severityCounts.medium,

          low:
            severityCounts.low,

          info:
            severityCounts.info
        },

        total_issues:
          issues.length,

        static_analysis: {
          status: "completed",

          total_issues:
            issues.length,

          issues: issues
        },

        llm_analysis: {
          status: "not_used",

          model:
            "llama3.2:latest",

          total_issues: 0,

          issues: []
        },

        issues: issues
      };

      setResult(
        convertedResult
      );

      setError("");

      setPage("results");

      saveToHistory(
        convertedResult
      );

    } catch (err) {
      console.error(
        "Git diff error:",
        err
      );

      if (
        err.response?.data?.detail
      ) {
        setError(
          err.response.data.detail
        );
      } else {
        setError(
          "Unable to analyze the Git diff."
        );
      }

    } finally {
      setLoading(false);
    }
  };

  // =========================================================
  // DOWNLOAD REPORT
  // =========================================================

  const downloadReport = () => {
    if (!result) {
      return;
    }

    const report = {
      project:
        "AI Code Reviewer",

      date:
        new Date().toLocaleString(),

      status:
        result.status,

      related:
        result.related,

      source:
        result.source,

      language:
        result.language,

      summary:
        result.summary,

      issues:
        result.issues || []
    };

    const blob = new Blob(
      [
        JSON.stringify(
          report,
          null,
          2
        )
      ],
      {
        type:
          "application/json"
      }
    );

    const url =
      URL.createObjectURL(
        blob
      );

    const link =
      document.createElement(
        "a"
      );

    link.href = url;

    link.download =
      "ai-code-review-report.json";

    document.body.appendChild(
      link
    );

    link.click();

    document.body.removeChild(
      link
    );

    URL.revokeObjectURL(
      url
    );
  };

  // =========================================================
  // CLEAR HISTORY
  // =========================================================

  const clearHistory = () => {
    localStorage.removeItem(
      "aiCodeReviewerHistory"
    );

    setHistory([]);
  };

  // =========================================================
  // HOME PAGE
  // =========================================================

  const renderHome = () => {
    return (
      <div className="page-container home-page">

        <section className="hero-section">

          <div className="hero-content">

            <div className="hero-badge">
              AI-POWERED CODE ANALYSIS
            </div>

            <h1>
              Review Your Code
              <span>
                Intelligently
              </span>
            </h1>

            <p>
              Analyze Python source code using
              static analysis and local AI.
              Detect security vulnerabilities,
              bugs and coding problems quickly.
            </p>

            <div className="hero-buttons">

              <button
                className="primary-button"
                onClick={() =>
                  setPage("analyze")
                }
              >
                Start Code Review
              </button>

              <button
                className="secondary-button"
                onClick={() =>
                  setPage("about")
                }
              >
                Learn More
              </button>

            </div>

          </div>


          <div className="hero-visual">

            <div className="code-window">

              <div className="window-header">
                <span></span>
                <span></span>
                <span></span>
              </div>

              <div className="code-lines">

                <div>
                  <span className="code-purple">
                    def
                  </span>{" "}
                  <span className="code-blue">
                    review_code
                  </span>
                  (code):
                </div>

                <div>
                  &nbsp;&nbsp;
                  <span className="code-purple">
                    if
                  </span>{" "}
                  code:
                </div>

                <div>
                  &nbsp;&nbsp;&nbsp;&nbsp;
                  analyze(code)
                </div>

                <div>
                  &nbsp;&nbsp;&nbsp;&nbsp;
                  <span className="code-purple">
                    return
                  </span>{" "}
                  result
                </div>

              </div>

              <div className="ai-scan">
                <span>
                  ✓
                </span>

                AI Analysis Ready
              </div>

            </div>

          </div>

        </section>


        

      </div>
    );
  };

  // =========================================================
  // ANALYZE PAGE
  // =========================================================

  const renderAnalyze = () => {
    return (
      <div className="page-container analyze-page">

        {/* ===================================================
            PAGE HEADER
        =================================================== */}

        <div className="analyze-header">

          <div className="analyze-label">
            CODE ANALYSIS
          </div>

          <h1>
            Analyze Your Code
          </h1>

          <p>
            Enter Python code, upload a Python file,
            or analyze a Git diff.
          </p>

        </div>


        {/* ===================================================
            01 ANALYZE CODE
        =================================================== */}

        <section className="analyze-primary-card">

          <div className="analyze-card-title-row">

            <div className="analyze-title-left">

              <div className="number-badge">
                01
              </div>

              <div>
                <h2>
                  Analyze Code
                </h2>

                <p>
                  Paste or type your source code below.
                </p>
              </div>

            </div>


            <div className="language-select">

              <label>
                Language
              </label>

              <select
                value={language}
                onChange={(e) =>
                  setLanguage(e.target.value)
                }
              >

                <option value="python">
                  Python
                </option>

                <option value="javascript">
                  JavaScript
                </option>

                <option value="java">
                  Java
                </option>

                <option value="cpp">
                  C++
                </option>

              </select>

            </div>

          </div>


          {/* CODE BOX */}

          <div className="code-box">

            <div className="code-box-top">

              <div className="code-file-name">

                <span className="code-file-dot"></span>

                source.py

              </div>

              <span className="code-language-label">
                {language.toUpperCase()}
              </span>

            </div>


            <textarea
              className="main-code-textarea"
              value={code}
              onChange={(e) =>
                setCode(e.target.value)
              }
              placeholder={`# Enter Python code here

def calculate(a, b):
    return a / b

result = calculate(10, 0)

print(result)`}
              spellCheck="false"
            />


            <div className="code-box-bottom">

              <div className="code-statistics">

                <span>
                  {code.length} characters
                </span>

                <span>
                  {code
                    ? code.split("\n").length
                    : 1} lines
                </span>

              </div>


              <button
                className="primary-button analyze-code-button"
                onClick={analyzeCode}
                disabled={loading}
              >

                {loading
                  ? "Analyzing..."
                  : "Analyze Code →"}

              </button>

            </div>

          </div>

        </section>


        {/* ===================================================
            02 AND 03
        =================================================== */}

        <div className="analyze-secondary-grid">


          {/* =================================================
              02 UPLOAD PYTHON FILE
          ================================================= */}

          <section className="analyze-secondary-card">

            <div className="secondary-card-header">

              <div className="secondary-number">
                02
              </div>

              <div>

                <h2>
                  Upload Python File
                </h2>

                <p>
                  Analyze an existing Python file.
                </p>

              </div>

            </div>


            <div className="file-upload-area">

              <div className="upload-icon">
                📁
              </div>

              <h3>
                {file
                  ? file.name
                  : "Upload a .py file"}
              </h3>

              <p>
                Only Python (.py) files are supported
              </p>


              <label className="file-input-button">

                Choose File

                <input
                  type="file"
                  accept=".py"
                  className="hidden-file-input"
                  onChange={(e) => {

                    const selectedFile =
                      e.target.files?.[0] ||
                      null;

                    setFile(
                      selectedFile
                    );

                    setError("");

                  }}
                />

              </label>

            </div>


            {file && (
              <div className="selected-file-name">
                ✓ {file.name}
              </div>
            )}


            <button
              className="secondary-action"
              onClick={analyzeFile}
              disabled={loading}
            >

              {loading
                ? "Analyzing..."
                : "Analyze File →"}

            </button>

          </section>


          {/* =================================================
              03 GIT DIFF
          ================================================= */}

          <section className="analyze-secondary-card">

            <div className="secondary-card-header">

              <div className="secondary-number">
                03
              </div>

              <div>

                <h2>
                  Git Diff
                </h2>

                <p>
                  Review only the changed code.
                </p>

              </div>

            </div>


            <div className="diff-editor-wrapper">

              <div className="diff-editor-header">

                <span>
                  git diff
                </span>

                <span>
                  DIFF
                </span>

              </div>


              <textarea
                className="diff-textarea"
                value={diff}
                onChange={(e) =>
                  setDiff(e.target.value)
                }
                placeholder={`@@ -1,3 +1,4 @@
 def login():
+    password = "admin123"
     return True`}
                spellCheck="false"
              />


              <div className="diff-footer">

                <span>
                  {diff.length} characters
                </span>

                <button
                  className="secondary-action"
                  onClick={analyzeDiff}
                  disabled={loading}
                >

                  {loading
                    ? "Analyzing..."
                    : "Analyze Git Diff →"}

                </button>

              </div>

            </div>

          </section>

        </div>


        {/* ===================================================
            ERROR
        =================================================== */}

        {error && (

          <div className="analyze-error">

            <span>
              !
            </span>

            {error}

          </div>

        )}

      </div>
    );
  };

  // =========================================================
  // RESULTS PAGE
  // =========================================================

  const renderResults = () => {

    if (!result) {

      return (
        <div className="page-container">

          <div className="empty-state">

            <div className="empty-icon">
              📋
            </div>

            <h2>
              No Results
            </h2>

            <p>
              Analyze Python code to see
              review results.
            </p>

            <button
              className="primary-button"
              onClick={newReview}
            >
              Start Review
            </button>

          </div>

        </div>
      );
    }


    // =======================================================
    // UNRELATED CONTENT
    // =======================================================

    const isUnrelated =
      result.status === "unrelated" ||
      result.related === false;


    if (isUnrelated) {

      const unrelatedSummary =
        result.summary || {};

      return (
        <div className="page-container results-page">

          <div className="results-top">

            <div>

              <div className="success-label">
                ! CONTENT NOT RELATED
              </div>

              <h1>
                Review Results
              </h1>

              <p>
                {result.language
                  ? result.language
                      .charAt(0)
                      .toUpperCase() +
                    result.language.slice(1)
                  : "Python"}

                {" • "}

                {result.source ||
                  "Code Editor"}
              </p>

            </div>


            <div className="results-actions">

              <button
                className="secondary-button"
                onClick={newReview}
              >
                + New Review
              </button>

            </div>

          </div>


          {/* SUMMARY */}

          <div className="summary-grid">

            <div className="summary-card">

              <div className="summary-icon">
                📋
              </div>

              <div>

                <span>
                  Total Issues
                </span>

                <strong>
                  {unrelatedSummary.total ?? 0}
                </strong>

              </div>

            </div>


            <div className="summary-card">

              <div className="summary-icon critical">
                🔴
              </div>

              <div>

                <span>
                  Critical
                </span>

                <strong>
                  {unrelatedSummary.critical ?? 0}
                </strong>

              </div>

            </div>


            <div className="summary-card">

              <div className="summary-icon high">
                🟠
              </div>

              <div>

                <span>
                  High
                </span>

                <strong>
                  {unrelatedSummary.high ?? 0}
                </strong>

              </div>

            </div>


            <div className="summary-card">

              <div className="summary-icon medium">
                🟡
              </div>

              <div>

                <span>
                  Medium
                </span>

                <strong>
                  {unrelatedSummary.medium ?? 0}
                </strong>

              </div>

            </div>


            <div className="summary-card">

              <div className="summary-icon low">
                🔵
              </div>

              <div>

                <span>
                  Low
                </span>

                <strong>
                  {unrelatedSummary.low ?? 0}
                </strong>

              </div>

            </div>

          </div>


          {/* ANALYSIS STATUS */}

          <div className="analysis-status-grid">

            <div className="analysis-status-card">

              <div className="analysis-status-icon">
                🔍
              </div>

              <div>

                <span>
                  Static Analysis
                </span>

                <strong>
                  0
                </strong>

                <small>
                  Not Analyzed
                </small>

              </div>

            </div>


            <div className="analysis-status-card">

              <div className="analysis-status-icon">
                🤖
              </div>

              <div>

                <span>
                  AI / Ollama
                </span>

                <strong>
                  0
                </strong>

                <small>
                  Not Analyzed
                </small>

              </div>

            </div>


            <div className="analysis-status-card">

              <div className="analysis-status-icon">
                🧠
              </div>

              <div>

                <span>
                  Model
                </span>

                <strong className="model-name">
                  Not Used
                </strong>

                <small>
                  Content Validation
                </small>

              </div>

            </div>

          </div>


          {/* VALIDATION */}

          <div className="results-section">

            <div className="section-heading">

              <span>
                CONTENT VALIDATION
              </span>

              <h2>
                Content could not be analyzed.
              </h2>

            </div>


            <div className="unrelated-result-card">

              <div className="unrelated-icon">
                !
              </div>

              <h2>
                Content Not Related
              </h2>

              <p>
                {result.message ||
                  "This content is not related to Python source code. Please enter valid Python code to analyze."}
              </p>

              <button
                className="primary-button"
                onClick={newReview}
              >
                Analyze Python Code
              </button>

            </div>

          </div>


          {/* SUBMITTED CONTENT */}

          <div className="results-section">

            <div className="section-heading">

              <span>
                REVIEWED CONTENT
              </span>

              <h2>
                Submitted Content
              </h2>

            </div>


            <div className="source-code-card">

              <pre>

                <code>
                  {result.code ||
                    "No content was submitted."}
                </code>

              </pre>

            </div>

          </div>

        </div>
      );
    }


    // =======================================================
    // NORMAL RESULTS
    // =======================================================

    const summary =
      result.summary || {};

    const issues =
      Array.isArray(result.issues)
        ? result.issues
        : [];

    const totalIssues =
      summary.total ??
      result.total_issues ??
      issues.length;

    const critical =
      summary.critical ?? 0;

    const high =
      summary.high ?? 0;

    const medium =
      summary.medium ?? 0;

    const low =
      summary.low ?? 0;

    const staticCount =
      result.static_analysis?.total_issues ??
      0;

    const aiCount =
      result.llm_analysis?.total_issues ??
      0;

    const model =
      result.llm_analysis?.model ||
      "Rule Based + AI";


    return (
      <div className="page-container results-page">

        {/* HEADER */}

        <div className="results-top">

          <div>

            <div className="success-label">
              ✓ REVIEW COMPLETE
            </div>

            <h1>
              Review Results
            </h1>

            <p>

              {result.language
                ? result.language
                    .charAt(0)
                    .toUpperCase() +
                  result.language.slice(1)
                : "Python"}

              {" • "}

              {result.source ||
                "Code Editor"}

            </p>

          </div>


          <div className="results-actions">

            <button
              className="secondary-button"
              onClick={downloadReport}
            >
              ↓ Download Report
            </button>

            <button
              className="secondary-button"
              onClick={newReview}
            >
              + New Review
            </button>

          </div>

        </div>


        {/* SUMMARY */}

        <div className="summary-grid">

          <div className="summary-card">

            <div className="summary-icon">
              📋
            </div>

            <div>

              <span>
                Total Issues
              </span>

              <strong>
                {totalIssues}
              </strong>

            </div>

          </div>


          <div className="summary-card">

            <div className="summary-icon critical">
              🔴
            </div>

            <div>

              <span>
                Critical
              </span>

              <strong>
                {critical}
              </strong>

            </div>

          </div>


          <div className="summary-card">

            <div className="summary-icon high">
              🟠
            </div>

            <div>

              <span>
                High
              </span>

              <strong>
                {high}
              </strong>

            </div>

          </div>


          <div className="summary-card">

            <div className="summary-icon medium">
              🟡
            </div>

            <div>

              <span>
                Medium
              </span>

              <strong>
                {medium}
              </strong>

            </div>

          </div>


          <div className="summary-card">

            <div className="summary-icon low">
              🔵
            </div>

            <div>

              <span>
                Low
              </span>

              <strong>
                {low}
              </strong>

            </div>

          </div>

        </div>


        {/* ANALYSIS STATUS */}

        <div className="analysis-status-grid">

          <div className="analysis-status-card">

            <div className="analysis-status-icon">
              🔍
            </div>

            <div>

              <span>
                Static Analysis
              </span>

              <strong>
                {staticCount}
              </strong>

              <small>
                AST / Rules
              </small>

            </div>

          </div>


          <div className="analysis-status-card">

            <div className="analysis-status-icon">
              🤖
            </div>

            <div>

              <span>
                AI / Ollama
              </span>

              <strong>
                {aiCount}
              </strong>

              <small>
                Local LLM
              </small>

            </div>

          </div>


          <div className="analysis-status-card">

            <div className="analysis-status-icon">
              🧠
            </div>

            <div>

              <span>
                Model
              </span>

              <strong className="model-name">
                {model}
              </strong>

              <small>
                Rule Based + AI
              </small>

            </div>

          </div>

        </div>


        {/* ISSUES */}

        <div className="results-section">

          <div className="section-heading">

            <span>
              DETECTED ISSUES
            </span>

            <h2>
              Problems detected during
              code analysis.
            </h2>

          </div>


          {issues.length === 0 ? (

            <div className="no-issues-card">

              <div className="no-issues-icon">
                ✓
              </div>

              <h2>
                No Issues Found
              </h2>

              <p>
                The submitted code passed
                the available security and
                bug checks.
              </p>

            </div>

          ) : (

            <div className="issues-list">

              {issues.map(
                (issue, index) => {

                  const severity =
                    String(
                      issue.severity ||
                      "medium"
                    ).toLowerCase();

                  return (

                    <div
                      className={`issue-card severity-${severity}`}
                      key={`${issue.rule_id || "issue"}-${index}`}
                    >

                      <div className="issue-number">
                        {index + 1}
                      </div>


                      <div className="issue-content">

                        <div className="issue-top">

                          <div>

                            <span
                              className={`severity-badge ${severity}`}
                            >
                              {severity.toUpperCase()}
                            </span>

                            <span className="rule-badge">
                              {issue.rule_id ||
                                "RULE"}
                            </span>

                          </div>


                          <span className="issue-line">
                            Line{" "}
                            {issue.line || 1}
                          </span>

                        </div>


                        <h3>
                          {issue.title ||
                            "Code Issue"}
                        </h3>


                        <p>
                          {issue.description ||
                            "Potential problem detected in the source code."}
                        </p>


                        {issue.suggestion && (

                          <div className="suggestion-box">

                            <strong>
                              Suggested Fix
                            </strong>

                            <span>
                              {issue.suggestion}
                            </span>

                          </div>

                        )}


                        {issue.detected_by && (

                          <div className="detected-by">

                            Detected by:{" "}

                            <strong>
                              {issue.detected_by}
                            </strong>

                          </div>

                        )}

                      </div>

                    </div>

                  );
                }
              )}

            </div>

          )}

        </div>


        {/* SOURCE CODE */}

        <div className="results-section">

          <div className="section-heading">

            <span>
              REVIEWED CODE
            </span>

            <h2>
              Source Code
            </h2>

          </div>


          <div className="source-code-card">

            {result.code ? (

              <pre>

                <code>
                  {result.code}
                </code>

              </pre>

            ) : (

              <div className="source-empty">
                Source code not available.
              </div>

            )}

          </div>

        </div>


        {/* AI MESSAGE */}

        {result.llm_analysis?.message && (

          <div className="ai-message-card">

            <div className="ai-message-icon">
              🤖
            </div>

            <div>

              <strong>
                AI / Ollama
              </strong>

              <p>
                {result.llm_analysis.message}
              </p>

            </div>

          </div>

        )}

      </div>
    );
  };

  // =========================================================
  // HISTORY PAGE
  // =========================================================

  const renderHistory = () => {
    return (
      <div className="page-container history-page">

        <div className="page-heading">

          <div>

            <div className="section-label">
              REVIEW HISTORY
            </div>

            <h1>
              Previous Reviews
            </h1>

            <p>
              View your previous Python code
              analysis results.
            </p>

          </div>


          {history.length > 0 && (

            <button
              className="secondary-button"
              onClick={clearHistory}
            >
              Clear History
            </button>

          )}

        </div>


        {history.length === 0 ? (

          <div className="empty-state">

            <div className="empty-icon">
              🕘
            </div>

            <h2>
              No Review History
            </h2>

            <p>
              Your completed Python code
              reviews will appear here.
            </p>

            <button
              className="primary-button"
              onClick={newReview}
            >
              Start First Review
            </button>

          </div>

        ) : (

          <div className="history-list">

            {history.map(
              (item) => (

                <div
                  className="history-card"
                  key={item.id}
                >

                  <div className="history-main">

                    <div className="history-icon">
                      {item.totalIssues === 0
                        ? "✓"
                        : "!"}
                    </div>

                    <div>

                      <h3>
                        {item.source ||
                          "Code Review"}
                      </h3>

                      <p>
                        {item.date}
                      </p>

                    </div>

                  </div>


                  <div className="history-stats">

                    <div>

                      <span>
                        Issues
                      </span>

                      <strong>
                        {item.totalIssues}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Critical
                      </span>

                      <strong>
                        {item.critical}
                      </strong>

                    </div>


                    <div>

                      <span>
                        High
                      </span>

                      <strong>
                        {item.high}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Medium
                      </span>

                      <strong>
                        {item.medium}
                      </strong>

                    </div>

                  </div>


                  <button
                    className="history-view-button"
                    onClick={() => {

                      setResult(
                        item.result
                      );

                      setPage(
                        "results"
                      );

                    }}
                  >
                    View
                  </button>

                </div>

              )
            )}

          </div>

        )}

      </div>
    );
  };

  // =========================================================
  // ABOUT PAGE
  // =========================================================

  const renderAbout = () => {
    return (
      <div className="page-container about-page">

        <div className="about-header">

          <div className="section-label">
            ABOUT THE PROJECT
          </div>

          <h1>
            AI Code Reviewer
          </h1>

          <p>
            Intelligent Python source code analysis
            using Static Analysis and Local AI.
          </p>

        </div>


        <div className="about-grid">

          <div className="about-main">

            <div className="about-card">

              <h2>
                What is AI Code Reviewer?
              </h2>

              <p>
                AI Code Reviewer is a software
                engineering project designed to
                automatically analyze Python source
                code and identify potential security
                vulnerabilities and programming bugs.
              </p>

              <p>
                The system combines Python AST-based
                static analysis with a locally running
                Ollama Large Language Model to provide
                an additional layer of intelligent code
                review.
              </p>

            </div>


            <div className="about-card">

              <h2>
                Technologies Used
              </h2>

              <div className="technology-list">

                <div className="technology-item">

                  <strong>
                    Frontend
                  </strong>

                  <span>
                    React.js
                  </span>

                </div>


                <div className="technology-item">

                  <strong>
                    Backend
                  </strong>

                  <span>
                    FastAPI
                  </span>

                </div>


                <div className="technology-item">

                  <strong>
                    Static Analysis
                  </strong>

                  <span>
                    Python AST
                  </span>

                </div>


                <div className="technology-item">

                  <strong>
                    AI
                  </strong>

                  <span>
                    Ollama + Llama 3.2
                  </span>

                </div>


                <div className="technology-item">

                  <strong>
                    Storage
                  </strong>

                  <span>
                    Browser LocalStorage
                  </span>

                </div>


                <div className="technology-item">

                  <strong>
                    API
                  </strong>

                  <span>
                    REST API
                  </span>

                </div>

              </div>

            </div>

          </div>


          <div className="about-side">

            <div className="about-highlight">

              <div className="highlight-icon">
                🔍
              </div>

              <h3>
                Static Analysis
              </h3>

              <p>
                Python source code is parsed using
                the Abstract Syntax Tree to identify
                known security and bug patterns.
              </p>

            </div>


            <div className="about-highlight">

              <div className="highlight-icon">
                🤖
              </div>

              <h3>
                Local AI
              </h3>

              <p>
                Ollama runs the language model
                locally, helping keep source code
                inside the local environment.
              </p>

            </div>


            <div className="about-highlight">

              <div className="highlight-icon">
                🛡️
              </div>

              <h3>
                Security First
              </h3>

              <p>
                The reviewer focuses on directly
                identifiable security vulnerabilities
                and programming bugs.
              </p>

            </div>

          </div>

        </div>


        <div className="about-footer-card">

          <h2>
            Built for Practical Code Review
          </h2>

          <p>
            The project demonstrates how traditional
            static code analysis and modern local AI
            can work together in a single developer
            tool.
          </p>

          <button
            className="primary-button"
            onClick={newReview}
          >
            Start Code Review
          </button>

        </div>

      </div>
    );
  };

  // =========================================================
  // NAVIGATION
  // =========================================================

  return (
    <div className="app">

      <header className="navbar">

        <div
          className="logo"
          onClick={() =>
            setPage("home")
          }
        >

          <div className="logo-icon">
            {"</>"}
          </div>

          <div className="logo-text">

            <strong>
              AI Code Reviewer
            </strong>

            <span>
              Intelligent Code Analysis
            </span>

          </div>

        </div>


        <nav>

          <button
            className={
              page === "home"
                ? "active"
                : ""
            }
            onClick={() =>
              setPage("home")
            }
          >
            Home
          </button>


          <button
            className={
              page === "analyze"
                ? "active"
                : ""
            }
            onClick={() =>
              setPage("analyze")
            }
          >
            Analyze
          </button>


          <button
            className={
              page === "results"
                ? "active"
                : ""
            }
            onClick={() =>
              setPage("results")
            }
          >
            Results
          </button>


          <button
            className={
              page === "history"
                ? "active"
                : ""
            }
            onClick={() =>
              setPage("history")
            }
          >
            History
          </button>


          <button
            className={
              page === "about"
                ? "active"
                : ""
            }
            onClick={() =>
              setPage("about")
            }
          >
            About
          </button>

        </nav>


        <button
          className="nav-analyze-button"
          onClick={newReview}
        >
          Analyze Code
        </button>

      </header>


      <main>

        {page === "home" &&
          renderHome()}

        {page === "analyze" &&
          renderAnalyze()}

        {page === "results" &&
          renderResults()}

        {page === "history" &&
          renderHistory()}

        {page === "about" &&
          renderAbout()}

      </main>


      <footer className="footer">

        <div>

          <strong>
            AI Code Reviewer
          </strong>

          <span>
            AI-powered Python code analysis
          </span>

        </div>

        <div>
          Built with React • FastAPI • Python • Ollama
        </div>

      </footer>

    </div>
  );
}

export default App;