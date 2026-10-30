"""Conservative source-level RTL checks and feature extraction for PPA-Insight."""
from __future__ import annotations
import re

FEATURE_LABELS = {
    "modules":"RTL modules", "registers":"Declared register/logic names", "wires":"Wire declarations",
    "multipliers":"Multiplication operators", "adders":"Addition operators", "subtractors":"Subtraction operators",
    "always_blocks":"Always blocks", "assign_statements":"Continuous assignments", "if_statements":"If statements",
    "case_blocks":"Case statements", "else_statements":"Else statements", "data_width":"WIDTH parameter (if detected)",
    "output_width":"First detected output width", "has_clock":"Clock-like identifier", "has_reset":"Reset-like identifier",
    "has_enable":"Enable-like identifier"
}


def strip_comments(code: str) -> str:
    # Preserve line breaks and avoid treating comment markers in strings as comments (basic lexer).
    code = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), code, flags=re.S)
    return re.sub(r"//[^\n]*", "", code)


def extract_features(code: str) -> dict[str, int]:
    code = strip_comments(code)
    modules = re.findall(r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_]\w*)", code)
    # Remove ANSI-style module port lists before counting body declarations, so
    # `input wire clk` is not mistaken for an internal wire declaration.
    body = re.sub(r"\bmodule\s+(?:automatic\s+|static\s+)?[A-Za-z_]\w*\s*(?:#\s*\([^;]*?\)\s*)?\([^;]*?\)\s*;", "", code, flags=re.S)
    reg_decls = re.findall(r"\b(?:reg|logic)\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([^;]+);", body)
    regs = set(re.findall(r"\boutput\s+(?:reg|logic)\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([A-Za-z_]\w*)", code))
    for declaration in reg_decls:
        for item in declaration.split(","):
            item = re.sub(r"\s*=.*", "", item).strip()
            match = re.search(r"([A-Za-z_]\w*)\s*$", item)
            if match: regs.add(match.group(1))
    wire_decls = re.findall(r"\bwire\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([^;]+);", body)
    wire_count = sum(len([x for x in d.split(",") if x.strip()]) for d in wire_decls)
    width_match = re.search(r"\bparameter\s+(?:integer\s+)?WIDTH\s*=\s*(\d+)", code, re.I)
    out_width = re.search(r"\boutput\b[^;\n]*?\[\s*(\d+)\s*:\s*(\d+)\s*\]", code)
    return {
        "modules": len(modules), "registers": len(regs), "wires": wire_count,
        "multipliers": len(re.findall(r"(?<!\*)\*(?!\*)", code)), "adders": len(re.findall(r"(?<!\+)\+(?!\+)", code)),
        "subtractors": len(re.findall(r"(?<!-)\-(?!-)", code)), "always_blocks": len(re.findall(r"\balways\s*@", code)),
        "assign_statements": len(re.findall(r"\bassign\b", code)), "if_statements": len(re.findall(r"\bif\s*\(", code)),
        "case_blocks": len(re.findall(r"\b(?:case|casex|casez)\s*\(", code)), "else_statements": len(re.findall(r"\belse\b", code)),
        "data_width": int(width_match.group(1)) if width_match else 0,
        "output_width": abs(int(out_width.group(1)) - int(out_width.group(2))) + 1 if out_width else 0,
        "has_clock": int(bool(re.search(r"\b(clk|clock|i_clk)\b", code, re.I))),
        "has_reset": int(bool(re.search(r"\b(reset|rst|reset_n|rst_n)\b", code, re.I))),
        "has_enable": int(bool(re.search(r"\b(enable|en|ce)\b", code, re.I))),
    }


def lint_rtl(code: str) -> list[dict[str, str]]:
    clean = strip_comments(code)
    findings: list[dict[str, str]] = []
    def add(level: str, check: str, evidence: str, suggestion: str) -> None:
        findings.append({"Level": level, "Check": check, "Evidence": evidence, "Suggested action": suggestion})
    if not re.search(r"\bmodule\s+[A-Za-z_]\w*", clean):
        add("Error", "Module declaration", "No module declaration detected.", "Add a valid module declaration before synthesis.")
    if len(re.findall(r"\bmodule\b", clean)) != len(re.findall(r"\bendmodule\b", clean)):
        add("Error", "Module boundaries", "module and endmodule counts differ.", "Check for missing or extra endmodule statements; use a parser/compiler to validate syntax.")
    if re.search(r"\balways\s*@\s*\(\s*\*\s*\)", clean) and re.search(r"\b(?:posedge|negedge)\b", clean):
        add("Review", "Procedural block style", "Both combinational and edge-triggered constructs were detected.", "Review each always block independently; prefer always_comb/always_ff where supported by your flow.")
    if re.search(r"\balways\s*@\s*\(\s*\*\s*\)", clean) and re.search(r"\b(?:always\s*@\s*\(\s*\*\s*\)[\s\S]*?\bif\b[\s\S]*?\bend\s*;)", clean):
        add("Review", "Potential incomplete assignment", "A combinational process with conditional logic was detected; this is not proof of a latch.", "Check that every assigned signal receives a value on every combinational path; confirm with synthesis warnings.")
    if re.search(r"\b(?:initial|force|release)\b", clean):
        add("Review", "Simulation-oriented constructs", "initial/force/release keyword detected.", "Confirm the selected FPGA/ASIC synthesis flow supports the construct.")
    if re.search(r"\b(?:real|realtime|time)\b", clean):
        add("Review", "Non-hardware data type", "A real/time-related type was detected.", "Verify synthesizability for the target flow.")
    if not findings:
        add("Info", "Static scan", "No high-confidence static issues detected by this lightweight scan.", "This is not a substitute for elaboration, lint, simulation or formal verification.")
    return findings
