from aae.code_analysis.dataflow import DataFlowAnalyzer
from aae.graph.ast_parser import ASTParser


class CodeAnalyzer:
    def __init__(self) -> None:
        self.parser = ASTParser()
        self.dataflow = DataFlowAnalyzer()

    def analyze(self, source: str):
        return {
            "structure": self.parser.parse(source),
            "flow": self.dataflow.analyze(source),
        }


__all__ = ["CodeAnalyzer", "DataFlowAnalyzer", "ASTParser"]
