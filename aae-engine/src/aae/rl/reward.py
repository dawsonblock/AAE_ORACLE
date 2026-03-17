def compute_rl_reward(before, after):
    """
    Computes reward based on failure reduction and efficiency.
    before/after: {'fail': count, 'patch_size': int}
    """
    reward = 0
    # Success signal
    reward += (before.get("fail", 0) - after.get("fail", 0)) * 2
    
    # Bonus for full resolution
    if after.get("fail", 0) == 0:
        reward += 10
        
    # Penalty for regressions
    if after.get("fail", 0) > before.get("fail", 0):
        reward -= 5
        
    # Efficiency penalty
    reward -= after.get("patch_size", 0) * 0.1
    return reward
