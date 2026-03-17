import json
import os

def save_profile(profile, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(profile.__dict__, f, indent=2)

def load_profile(path, cls):
    obj = cls()
    if not os.path.exists(path):
        return obj
    with open(path) as f:
        data = json.load(f)
    obj.__dict__.update(data)
    return obj
