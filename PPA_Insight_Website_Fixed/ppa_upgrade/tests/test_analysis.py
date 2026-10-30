import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rtl_analysis import extract_features, lint_rtl
from synthesis_engine import _cell_metrics, make_vivado_tcl, parse_rtl_modules, parse_vivado_reports


class RTLAnalysisTests(unittest.TestCase):
    def test_counter8_module_and_features(self):
        source = (ROOT / "examples" / "counter8.v").read_text(encoding="utf-8")
        self.assertEqual(parse_rtl_modules(source), ["counter8"])
        features = extract_features(source)
        self.assertEqual(features["modules"], 1)
        self.assertEqual(features["registers"], 1)
        self.assertEqual(features["output_width"], 8)
        self.assertEqual(features["always_blocks"], 1)
        self.assertEqual(features["has_clock"], 1)

    def test_comments_do_not_create_modules(self):
        self.assertEqual(parse_rtl_modules("// module fake;\nmodule real; endmodule"), ["real"])

    def test_vivado_report_parser_preserves_available_metrics(self):
        result = parse_vivado_reports("CLB LUTs | 123", "WNS (ns) -0.12\nTNS (ns) -3.2", "Total On-Chip Power (W) 1.23")
        self.assertEqual(result["metrics"]["LUTs"], 123.0)
        self.assertEqual(result["metrics"]["WNS_ns"], -0.12)
        self.assertEqual(result["metrics"]["Estimated_Total_Power_W"], 1.23)

    def test_yosys_cell_classification(self):
        metrics, cells = _cell_metrics({"a": {"type": "LUT3"}, "b": {"type": "FDRE"}, "c": {"type": "DSP48E1"}})
        self.assertEqual(metrics["LUTs (mapped)"], 1)
        self.assertEqual(metrics["Flip-flops (mapped)"], 1)
        self.assertEqual(metrics["DSP blocks"], 1)
        self.assertEqual(len(cells), 3)

    def test_vivado_tcl_has_clock_guard(self):
        script = make_vivado_tcl("counter8", "counter8.v", "xc7a35tcpg236-1", 10)
        self.assertIn("synth_design -top $TOP -part $PART", script)
        self.assertIn("if {[llength $clk_port] > 0}", script)

    def test_bad_top_is_rejected(self):
        with self.assertRaises(ValueError):
            make_vivado_tcl("bad top", "counter8.v", "xc7a35tcpg236-1", 10)


if __name__ == "__main__":
    unittest.main()
