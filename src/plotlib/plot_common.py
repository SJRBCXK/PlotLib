





def color_positions(sample_idx):
    
    return {sample: i / (len(set(sample_idx))) for i, sample in enumerate(sorted(set(sample_idx)))}
