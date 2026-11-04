"""Build final-v1 once, without model calls; witnesses are audit-only, never planner inputs."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_scenarios import find_feasible_plan
from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.schemas import Scenario, load_places, load_tag_catalog, load_travel_times

# Distinct preference structures; budget variants within a family are dependent.
# Each friend retains culture as an attainable interest even when another like conflicts.
TEMPLATES = [
 (2, 1, 'straightforward', [], [['food','culture'], ['shopping','outdoor','culture']], 18, 50),
 (2, 2, 'straightforward', [], [['outdoor','culture'], ['food','shopping','culture']], 25, 65),
 (2, 2, 'conflicting', ['no_temples'], [['temples','outdoor','culture'], ['shopping','culture']], 25, 60),
 (2, 2, 'highly_constrained', ['no_temples','no_nightlife','no_early_mornings'], [['hiking','food','culture'], ['nightlife','shopping','culture']], 32, 70),
 (3, 1, 'straightforward', ['no_early_mornings'], [['food','culture'], ['outdoor','culture'], ['shopping','nightlife','culture']], 18, 55),
 (3, 2, 'conflicting', ['no_nightlife'], [['nightlife','food','culture'], ['temples','culture'], ['shopping','outdoor','culture']], 20, 65),
 (3, 2, 'conflicting', ['no_temples'], [['temples','shopping','culture'], ['hiking','outdoor','culture'], ['food','nightlife','culture']], 25, 75),
 (5, 2, 'straightforward', [], [['food','culture'], ['outdoor','culture'], ['temples','culture'], ['shopping','culture'], ['nightlife','culture']], 18, 70),
 (5, 2, 'conflicting', ['no_temples','no_nightlife'], [['temples','food','culture'], ['nightlife','outdoor','culture'], ['shopping','culture'], ['hiking','food','culture'], ['outdoor','shopping','culture']], 30, 85),
 (5, 3, 'highly_constrained', ['no_temples','no_nightlife','no_early_mornings'], [['hiking','outdoor','culture'], ['nightlife','shopping','culture'], ['temples','food','culture'], ['food','outdoor','culture'], ['shopping','outdoor','culture']], 48, 100),
]

def signature(s):
    return (s.days, tuple(sorted((tuple(sorted(p.likes)), tuple(sorted(p.hard_limits))) for p in s.friends.values())))

def build(output):
    if output.exists():
        raise ValueError('refuse to overwrite final dataset')
    config = load_config(ROOT/'config.yaml', [])
    places = load_places(ROOT/config['paths']['places'])
    travel = load_travel_times(ROOT/config['paths']['travel_times'])
    catalog = load_tag_catalog(ROOT/config['paths']['tags'])
    prior = set()
    # Includes previously evaluated inputs; ignore non-scenario metadata files.
    for base in (ROOT/'data', ROOT/'results'):
        for path in base.rglob('*.json'):
            if 'source' in path.parts or '.cache' in path.parts:
                continue
            try:
                prior.add(signature(Scenario.model_validate_json(path.read_text())))
            except (ValueError, OSError):
                pass
    scenarios, entries, witnesses = {}, {}, {}
    for index, (n, days, kind, limits, likes, tight, loose) in enumerate(TEMPLATES, 1):
        for variant, cap in (('tight', tight), ('loose', loose)):
            sid = f'final_v1_{index:02d}_{variant}'
            friends = {f'Friend_{i+1}': {'likes': tags, 'hard_limits': [], 'budget': cap+i}
                       for i, tags in enumerate(likes)}
            for i, limit in enumerate(limits):
                friends[f'Friend_{i % n + 1}']['hard_limits'].append(limit)
            scenario = Scenario.model_validate(dict(id=sid, split='heldout', days=days, n_friends=n,
                conflict='mild' if kind=='straightforward' else 'strong', budget=variant, friends=friends))
            if signature(scenario) in prior:
                raise ValueError('pre-existing preference/day template: '+sid)
            plan = find_feasible_plan(scenario, places, travel, catalog, config['day_start'], config['day_end'], 2)
            if plan is None:
                raise ValueError('no feasible witness: '+sid)
            report = check_plan(plan, scenario.friends, places, travel, {**config, 'days': days})
            if not report.task_success or report.fairness.min <= 0:
                raise ValueError('witness must pass and give every friend positive satisfaction: '+sid)
            content = json.dumps(scenario.model_dump(), indent=2)+'\n'
            scenarios[sid] = content
            entries[sid] = dict(family_id=f'final_family_{index:02d}', template_id=f'final_template_{index:02d}',
                difficulty=kind, budget_variant=variant, n_friends=n, days=days, expected_feasible=True,
                sha256=hashlib.sha256(content.encode()).hexdigest())
            witnesses[sid] = dict(plan=plan.model_dump(), report=report.model_dump())
    output.mkdir(parents=True)
    (output/'heldout').mkdir()
    for sid, content in scenarios.items():
        (output/'heldout'/f'{sid}.json').write_text(content)
    manifest = dict(dataset='kyoto-final-v1', design='10 families x 2 budget variants; all feasible',
        generation='deterministic, no LLM; new profile/day structures checked against existing data and result inputs',
        shared_interest='Every profile includes culture; positive-minimum witnesses establish nondegenerate attainable utility.',
        limitations='Constructed Kyoto benchmark, not random population sampling; family variants are dependent.',
        checker_config={k: config[k] for k in ('day_start','day_end','min_activities_per_day')},
        world_hashes={k: hashlib.sha256((ROOT/config['paths'][k]).read_bytes()).hexdigest() for k in ('places','tags','travel_times')},
        scenarios=entries)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output/'witnesses.json').write_text(json.dumps(witnesses, indent=2)+'\n')
    print(f'Validated {len(entries)} feasible scenarios in {output}; no model calls.')

if __name__ == '__main__':
    build(ROOT/'data/final_eval_v1')
