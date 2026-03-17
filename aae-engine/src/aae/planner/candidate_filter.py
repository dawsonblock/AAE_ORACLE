class CandidateFilter:
    def filter(self, candidates):
        """Removes repairs that exceed complexity or file-count thresholds."""
        filtered = []
        for c in candidates:
            # Rule: Don't allow patches that modify more than 3 files
            if c.get("files_modified", 1) > 3:
                continue
            
            # Rule: Patch size limit
            if c.get("changes", 0) > 5000:
                continue
                
            filtered.append(c)
        return filtered
