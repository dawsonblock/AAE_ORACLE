from tree_sitter import Language, Parser

class MultiParser:
    def __init__(self, lib_path="build/my-languages.so"):
        # Note: In a real environment, these must be built via script
        try:
            self.languages = {
                "python": Language(lib_path, "python"),
                "javascript": Language(lib_path, "javascript"),
            }
        except Exception as e:
            print(f"Warning: could not load tree-sitter languages: {e}")
            self.languages = {}

    def parse(self, code: str, lang: str):
        if lang not in self.languages:
            return None
        parser = Parser()
        parser.set_language(self.languages[lang])
        return parser.parse(bytes(code, "utf8"))
