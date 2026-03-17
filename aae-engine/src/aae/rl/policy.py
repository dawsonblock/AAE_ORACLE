import random


class Policy:
    def __init__(self, epsilon=0.2):
        self.q = {}
        self.epsilon = epsilon

    def _key(self, state, action):
        return f"{state}|{action}"

    def select(self, state, actions):
        if random.random() < self.epsilon:
            return random.choice(actions)

        best_action = None
        best_value = float("-inf")
        for action in actions:
            value = self.q.get(self._key(state, action), 0.0)
            if value > best_value:
                best_value = value
                best_action = action
        return (
            best_action if best_action is not None
            else random.choice(actions)
        )
