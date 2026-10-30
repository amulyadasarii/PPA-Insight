# PPA-Insight | RTL-to-FPGA Resource Analysis Workbench

**PPA-Insight** is an ECE/VLSI academic prototype for examining Verilog RTL structure, synthesizing designs, inspecting mapped logic resources, reviewing timing/power reports, and exploring an experimental LUT-estimation baseline.

It is designed as an engineering decision-support tool. It does not replace RTL simulation, formal equivalence, Vivado implementation, timing sign-off, or board-level power measurement.

## Implemented capabilities

| Block | What the prototype does | Evidence type |
|---|---|---|
| RTL intake | Accepts Verilog/SystemVerilog source and selects a top module | User-provided RTL |
| RTL structural analysis | Extracts operator, declaration, procedural-block, width and control indicators | Lightweight source-level heuristic |
| Static review | Flags selected RTL patterns for engineering review | Heuristic; not a full HDL linter |
| Yosys synthesis | Runs generic synthesis or attempts Xilinx 7-series mapping when supported | Synthesized netlist/tool output |
| Netlist inspection | Summarizes cell types and top-level ports | Yosys JSON/netlist evidence |
| Vivado handoff | Generates a Tcl script for synthesis and utilization/timing/power report generation | Requires local Vivado and correct constraints |
| Vivado report import | Extracts selected metrics from uploaded reports | Best-effort parsing; verify original reports |
| ML baseline | Demonstrates Random Forest LUT estimation using the bundled small dataset | Experimental; not independently validated |
| Optimization review | Produces conservative RTL review prompts | Candidate suggestions, not proven improvements |
| Exports | Produces Markdown assessment, feature CSV and synthesis evidence JSON | Reproducibility support |

## VLSI workflow

1. Select the RTL source and top module.
2. Review the RTL structure and static findings.
3. Run Yosys synthesis. Use generic synthesis for technology-independent logic statistics, or the `xc7` flow only if the installed Yosys build supports Xilinx 7-series mapping.
4. For FPGA-specific resource and timing evidence, open the design in Vivado and use the correct FPGA part and timing constraints.
5. Inspect utilization, timing and power reports in Vivado. Import the original reports into PPA-Insight if desired.
6. Make one RTL change at a time, run functional verification, and repeat synthesis with identical tool settings.
7. Compare the baseline and modified design using like-for-like evidence.

## Installation (Windows)

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`.

### Optional Yosys setup

Install Yosys or OSS CAD Suite and ensure `yosys.exe` is available on `PATH`. Alternatively, set `YOSYS_BIN` in PowerShell:

```powershell
$env:YOSYS_BIN = "C:\path\to\oss-cad-suite\bin\yosys.exe"
python -m streamlit run app.py
```

Check installation with `yosys -V` in the same terminal used to start Streamlit.

### Vivado

Vivado is not bundled with this project. The dashboard can generate a Tcl handoff script and source file. Review the script before running it. The default example part and clock port are placeholders and must be changed to match the actual FPGA board/design.

## Dataset and ML scope

The bundled CSV is a small, mixed-source project dataset. It contains some rows with LUT/resource labels and fewer rows with timing or power labels. It is suitable for demonstrating data handling and an experimental Random Forest LUT estimator, **not** for claiming robust predictive accuracy or generalization.

- The current ML model estimates LUT count only.
- It does not predict power or timing.
- Feature importance is not SHAP, causal sensitivity, or proof that an RTL edit will improve PPA.
- Do not combine generic Yosys cell counts and FPGA LUT counts as if they were the same metric.
- Compare metrics only when device, tool version, constraints and implementation stage are compatible.

## Important engineering limitations

- RTL feature extraction uses lightweight pattern matching, not a complete Verilog/SystemVerilog compiler.
- Static review results are prompts, not proof of synthesizability, latch inference or functional correctness.
- Generic Yosys cells are not equivalent to FPGA LUTs.
- Timing reports are meaningful only with valid clock and I/O constraints. Post-synthesis timing is not post-route timing closure.
- Power estimates depend on device, implementation stage, clocks and switching activity assumptions. They are not board measurements.
- The application does not run a functional testbench or formal equivalence flow automatically.
- Optimization recommendations are hypotheses. Demonstrate benefit with verified before/after experiments.

## Project structure

```text
app.py                         Streamlit VLSI workbench
src/rtl_analysis.py            RTL feature extraction and static review
src/synthesis_engine.py        Yosys runner, Vivado Tcl generation and report parsing
src/yosys_analyzer.py          Standalone Yosys synthesis runner
src/netlist_analyzer.py        Netlist cell-statistics utility
src/benchmark_runner.py        Benchmark utility
dataset/final_merged_dataset.csv Bundled research dataset
examples/counter8.v            Example RTL module
tests/                         Automated helper tests
docs/                          Final demonstration and validation guidance
```

## Verification

Run the included helper tests from the project root:

```powershell
python -m unittest discover -s tests -v
```

These tests validate helper functions only. They do not constitute a live Yosys/Vivado run or functional verification of every benchmark design.

## Suggested academic description

“PPA-Insight is a prototype RTL analysis and FPGA resource-assessment workbench that combines source-level feature extraction, Yosys synthesis evidence, Vivado report integration, an experimental LUT-estimation baseline and rule-based RTL review prompts.”

Use this description rather than claiming a validated multi-objective PPA prediction or automatic RTL optimization system.


## Final demonstration update — 30 October 2026

### Project team
- Amulya Reddy — 23R21A04D9
- G. Aravind — 23R21A04E4
- G. Ajay — 23R21A04E7

### Latest Vivado benchmark evidence
The dataset now includes screenshot-derived results for six designs: MAC, ALU, barrel shifter, comparator, counter and priority encoder. See `dataset/vivado_ppa_results.csv` for the consolidated view and `dataset/final_merged_dataset.csv` for the model input dataset.

### Evidence and interpretation
- WNS and WHS are timing slack metrics. They are not direct maximum propagation-delay measurements.
- Power values are Vivado estimates, not bench-measured power.
- Most power values supplied for this update are from synthesized-netlist reports; the MAC power figure is from an implemented-netlist report. Do not treat these as directly comparable without rerunning a consistent flow.
- The ALU, barrel shifter, comparator and priority encoder reports show low power confidence and dominant I/O contributions. Counter power confidence is medium.
- Some Check Timing reports show partial or missing external I/O delay constraints. The consolidated CSV records these limitations rather than hiding them.
- The six-design dataset is a small academic prototype dataset. It is not sufficient to claim robust generalization or validated ML prediction accuracy.

### Motion design
The dashboard includes restrained fade/slide-in motion and subtle team-card emphasis. CSS respects `prefers-reduced-motion` accessibility settings.
