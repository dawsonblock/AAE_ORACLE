from typing import List


class Mutator:
    def mutate_patch(self, patch: str) -> List[str]:
        variants = {patch}

        variants.add(patch.replace(" is None", " == None"))
        variants.add(patch.replace("return", "return None"))
        variants.add(patch + "\n# mutation")
        variants.add(patch.replace("raise ValueError('guard failed')", "return"))

        return [v for v in variants if v.strip()]
