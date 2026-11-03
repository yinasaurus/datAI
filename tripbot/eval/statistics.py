"""Scenario-first differences and family-cluster percentile bootstrap (offline only)."""
from collections import defaultdict
from random import Random
from statistics import mean


def cluster_interval(differences, families, *, seed=42, resamples=1000):
    """Resample whole families, retaining all member scenario differences each draw.

    The point estimator weights scenarios equally. Bootstrap draws preserve family
    sizes; a ratio of sums handles unequal cluster sizes. No run is a sampling unit.
    """
    groups = defaultdict(list)
    for scenario, difference in differences.items():
        if scenario not in families:
            return None, None, 0
        groups[families[scenario]].append(difference)
    names = sorted(groups)
    if len(names) < 2:
        return None, None, len(names)
    rng = Random(seed)
    samples = sorted(mean(v for name in rng.choices(names, k=len(names)) for v in groups[name])
                     for _ in range(resamples))
    def quantile(p):
        index = p * (len(samples)-1)
        low = int(index)
        return samples[low] + (samples[min(low+1, len(samples)-1)]-samples[low])*(index-low)
    return quantile(.025), quantile(.975), len(names)
