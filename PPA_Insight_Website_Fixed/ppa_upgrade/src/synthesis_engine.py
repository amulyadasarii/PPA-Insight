"""Reproducible synthesis helpers for PPA-Insight.

Yosys results are measured from a generated netlist. Vivado support creates a
portable Tcl run script and parses user-supplied reports; it never invents
physical timing or power values.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


def find_yosys() -> str | None:
    """Locate Yosys using YOSYS_BIN, PATH, then common OSS CAD Suite paths."""
    configured = os.environ.get("YOSYS_BIN")
    candidates = [configured, shutil.which("yosys"), shutil.which("yosys.exe")]
    if os.name == "nt":
        candidates += [
            r"C:\oss-cad-suite\bin\yosys.exe",
            str(Path.home() / "Downloads" / "oss-cad-suite" / "bin" / "yosys.exe"),
        ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return None


def _quote_yosys(path: Path) -> str:
    # Yosys script paths use double quotes; reject newline and quote injection.
    value = str(path.resolve())
    if any(c in value for c in ['"', '\n', '\r']):
        raise ValueError("File path contains unsupported characters for a Yosys script.")
    return '"' + value.replace('\\', '/') + '"'


def parse_rtl_modules(source: str) -> list[str]:
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    return re.findall(r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_]\w*)", source)


def _cell_metrics(cells: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = Counter(str(cell.get("type", "UNKNOWN")) for cell in cells.values())
    lut = sum(n for t, n in counts.items() if re.fullmatch(r"(?:LUT[1-6]|SB_LUT4|\$_LUT_)", t, re.I))
    ffs = sum(n for t, n in counts.items() if re.search(r"(?:^FD|DFF|DFFE|SDFF|\$_DFF|\$_SDFF|\$_DFFE|\$_SDFFE)", t, re.I))
    dsps = sum(n for t, n in counts.items() if re.search(r"DSP|MULT18|MULT9", t, re.I))
    brams = sum(n for t, n in counts.items() if re.search(r"RAMB|BRAM|\$_(D|T)PRAM", t, re.I))
    carry = sum(n for t, n in counts.items() if re.search(r"CARRY|ALU", t, re.I))
    # If technology-independent cells are present, report their count as logic
    # cells rather than mislabelling them as FPGA LUTs.
    mapped_lut_count = lut if lut else None
    metrics = {
        "Synthesized cells": len(cells),
        "LUTs (mapped)": mapped_lut_count,
        "Flip-flops (mapped)": ffs,
        "DSP blocks": dsps,
        "BRAM blocks": brams,
        "Carry/ALU cells": carry,
        "Distinct cell types": len(counts),
    }
    breakdown = [{"Cell type": t, "Count": n} for t, n in sorted(counts.items())]
    return metrics, breakdown


def run_yosys(source: str, top: str, target: str = "Generic synthesis", timeout: int = 180) -> dict[str, Any]:
    """Run Yosys in an isolated temporary directory and return measured results."""
    binary = find_yosys()
    if not binary:
        raise FileNotFoundError(
            "Yosys was not found. Install Yosys/OSS CAD Suite, add it to PATH, or set YOSYS_BIN to the executable path."
        )
    modules = parse_rtl_modules(source)
    if top not in modules:
        raise ValueError(f"Top module '{top}' was not found. Modules detected: {', '.join(modules) or 'none'}")
    if not source.strip():
        raise ValueError("RTL source is empty.")

    with tempfile.TemporaryDirectory(prefix="ppa_insight_") as temp:
        work = Path(temp)
        rtl = work / "design.v"
        netlist = work / "netlist.json"
        rtl.write_text(source, encoding="utf-8")
        read_cmd = f"read_verilog -sv {_quote_yosys(rtl)}"
        if target == "Xilinx 7-series (xc7)":
            commands = [read_cmd, f"hierarchy -check -top {top}", "proc", "opt", "check", f"synth_xilinx -family xc7 -top {top}", "check", f"write_json {_quote_yosys(netlist)}", "stat"]
        else:
            commands = [read_cmd, f"hierarchy -check -top {top}", "proc", "opt", "check", f"synth -top {top}", "check", f"write_json {_quote_yosys(netlist)}", "stat"]
        script = work / "run.ys"
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(
                [binary, "-Q", "-T", "-s", str(script)], cwd=str(work),
                capture_output=True, text=True, errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Yosys exceeded the {timeout}-second timeout.") from exc
        log = (result.stdout or "") + ("\n--- STDERR ---\n" + result.stderr if result.stderr else "")
        if result.returncode != 0 or not netlist.exists():
            raise RuntimeError(f"Yosys synthesis failed (exit {result.returncode}).\n\n{log[-12000:]}")
        payload = json.loads(netlist.read_text(encoding="utf-8"))
        if top not in payload.get("modules", {}):
            raise RuntimeError(f"Top module '{top}' was absent from the generated netlist.\n{log[-4000:]}")
        module = payload["modules"][top]
        metrics, breakdown = _cell_metrics(module.get("cells", {}))
        return {
            "tool": "Yosys", "target": target, "top": top, "status": "Success",
            "metrics": metrics, "cell_breakdown": breakdown,
            "ports": [{"Port": name, "Direction": p.get("direction", "unknown"), "Bits": len(p.get("bits", []))} for name, p in module.get("ports", {}).items()],
            "log": log[-16000:], "version": _version(binary),
            "note": "Counts are measured from the synthesized JSON netlist. Generic synthesis cell counts are not FPGA LUT counts; timing and power are not computed by this flow.",
        }


def _version(binary: str) -> str:
    try:
        result = subprocess.run([binary, "-V"], capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip().splitlines()[0][:200]
    except Exception:
        return "Version unavailable"


def make_vivado_tcl(top: str, source_filename: str, part: str, clock_ns: float) -> str:
    """Create a Tcl script the user can run inside Vivado with their RTL file."""
    if not re.fullmatch(r"[A-Za-z_]\w*", top):
        raise ValueError("Top module must be a valid Verilog identifier.")
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", part):
        raise ValueError("FPGA part contains unsupported characters.")
    if not (0.1 <= float(clock_ns) <= 1000):
        raise ValueError("Clock period must be between 0.1 ns and 1000 ns.")
    safe_file = Path(source_filename).name
    if not safe_file.endswith((".v", ".sv", ".vh")):
        raise ValueError("Source filename must be a Verilog/SystemVerilog file.")
    return f'''# PPA-Insight generated Vivado synthesis/implementation script
# Run from the directory containing {safe_file} in Vivado Tcl Console.
# Replace PART if necessary for your actual FPGA device.
set TOP {{{top}}}
set PART {{{part}}}
set RTL_FILE {{{safe_file}}}
set OUT_DIR ./ppa_insight_vivado_reports
file mkdir $OUT_DIR
read_verilog -sv $RTL_FILE
synth_design -top $TOP -part $PART
report_utilization -file $OUT_DIR/utilization.rpt
set clk_port [get_ports -quiet clk]
if {{[llength $clk_port] > 0}} {{
    create_clock -name ppa_insight_clk -period {float(clock_ns):.4f} $clk_port
}} else {{
    puts "WARNING: no top-level port named clk found; timing results may be unconstrained."
}}
report_timing_summary -delay_type max -report_unconstrained -file $OUT_DIR/timing_summary.rpt
report_power -file $OUT_DIR/power.rpt
write_checkpoint -force $OUT_DIR/post_synth.dcp
puts "PPA-Insight reports written to $OUT_DIR"
'''


def parse_vivado_reports(utilization: str = "", timing: str = "", power: str = "") -> dict[str, Any]:
    """Best-effort parse of common Vivado text report labels; unknowns stay absent."""
    combined = "\n".join([utilization, timing, power])
    metrics: dict[str, float] = {}
    patterns = {
        "LUTs": [r"(?:CLB LUTs|Slice LUTs|LUT as Logic)\s*\|?\s*([\d,]+)"],
        "Registers": [r"(?:CLB Registers|Slice Registers|Register as Flip Flop)\s*\|?\s*([\d,]+)"],
        "DSPs": [r"(?:DSPs|DSPs\s*\(\w+\))\s*\|?\s*([\d,]+)"],
        "BRAMs": [r"(?:Block RAM Tile|Block RAMs)\s*\|?\s*([\d,.]+)"],
        "WNS_ns": [r"WNS\s*\(ns\)\s*[:|]?\s*(-?\d+(?:\.\d+)?)", r"Worst Negative Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)"],
        "TNS_ns": [r"TNS\s*\(ns\)\s*[:|]?\s*(-?\d+(?:\.\d+)?)", r"Total Negative Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)"],
        "Estimated_Total_Power_W": [r"Total On-Chip Power \(W\)\s*[:|]?\s*(\d+(?:\.\d+)?)", r"Total Power\s*[:=]?\s*(\d+(?:\.\d+)?)\s*W"],
    }
    for name, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, combined, re.I | re.M)
            if match:
                try:
                    metrics[name] = float(match.group(1).replace(",", ""))
                    break
                except ValueError:
                    pass
    sources = {"utilization": bool(utilization.strip()), "timing": bool(timing.strip()), "power": bool(power.strip())}
    return {"metrics": metrics, "sources": sources, "note": "Report parsing is best-effort. Verify parsed values against the original Vivado report before citing them."}
