# Final Project Demonstration Checklist

## Before the demonstration

- [ ] Open the project folder in VS Code and confirm `app.py`, `src/`, `dataset/`, `examples/` and `tests/` are present.
- [ ] Activate the virtual environment and launch Streamlit.
- [ ] Keep the actual RTL source files and Vivado project/report files in a separate clearly named folder. This ZIP contains only `examples/counter8.v`; it does not include the full set of benchmark RTL files or a Vivado project.
- [ ] Confirm the exact FPGA part number from the board/device used in Vivado.
- [ ] Confirm the top module and clock port name.
- [ ] Keep the original Vivado utilization, timing and power reports available.
- [ ] Run the helper tests: `python -m unittest discover -s tests -v`.

## Recommended live demonstration sequence

1. Upload one of the actual project benchmark RTL files and select its top module.
2. Show the RTL feature inventory and explain that these counts are source-level indicators.
3. Run Yosys synthesis if it is installed. Show the synthesized cell breakdown and clarify whether the target is generic or Xilinx-mapped.
4. Open the same design in Vivado. Show the RTL/elaborated or synthesized schematic that you actually generated.
5. Show the utilization report (LUT, FF/register, DSP and BRAM where applicable).
6. Show timing summary only after confirming the clock constraint and report stage. Explain WNS/TNS using the actual report.
7. Show power only with the report's assumptions and activity source stated.
8. Show the ML tab as an experimental LUT-estimation baseline, not a validated predictor.
9. Show the optimization review queue as candidate engineering checks, not guaranteed improvements.
10. Export the assessment report and point out its evidence labels.

## What to say about the VLSI contribution

- RTL is the design-entry representation.
- Feature extraction summarizes structural characteristics such as arithmetic operators, procedural blocks and declared signals.
- Yosys converts RTL into a synthesized netlist for cell-level inspection.
- Vivado maps the design to the selected FPGA architecture and reports device-specific resource utilization and timing.
- PPA-Insight brings source-level analysis, synthesis evidence and report review into one workflow.

## Do not claim unless you have evidence

- Accurate prediction of power or timing by the ML model.
- Validated SHAP/module-level sensitivity analysis.
- Automatic RTL rewriting or optimization.
- Timing closure from synthesis-only WNS.
- Measured board power from an estimated Vivado power report.
- Functional correctness without simulation/formal evidence.

## Useful evidence to keep ready

- RTL source for each demonstrated design.
- Vivado project or Tcl build script.
- Synthesis/utilization report.
- Timing summary and the XDC constraints used.
- Power report and activity assumptions, if available.
- Testbench and simulation waveform, if available.
- Before/after reports for any optimization you claim improved PPA.
