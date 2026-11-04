"""No-network checks of final dataset, denominator semantics and dependent analysis."""
import hashlib
import json
from pathlib import Path

import pytest
from tripbot.checker.check_plan import check_plan
from tripbot.config import load_config
from tripbot.eval.run import main
from tripbot.eval.statistics import cluster_interval
from tripbot.eval.summarise import condition_summary, paired_summary
from tripbot.planning.prompts import GROUP_CONSTRAINTS, setup_a_prompt, mediator_prompt
from tripbot.schemas import Plan, load_places, load_scenario, load_travel_times

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/final_eval_v1'


def test_final_dataset_witnesses_and_shared_prompt_requirements():
    metadata = json.loads((DATA/'manifest.json').read_text())
    witnesses = json.loads((DATA/'witnesses.json').read_text())
    config = load_config(ROOT/'config.yaml', [])
    places = load_places(ROOT/config['paths']['places'])
    travel = load_travel_times(ROOT/config['paths']['travel_times'])
    assert len(metadata['scenarios']) == 20
    assert len({m['family_id'] for m in metadata['scenarios'].values()}) == 10
    for sid, entry in metadata['scenarios'].items():
        path = DATA/'heldout'/f'{sid}.json'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        scenario = load_scenario(path)
        cfg = {**config, 'days': scenario.days}
        report = check_plan(Plan.model_validate(witnesses[sid]['plan']), scenario.friends, places, travel, cfg)
        assert report.task_success and report.fairness.min > 0
        assert GROUP_CONSTRAINTS in setup_a_prompt(scenario.friends, places, travel, cfg)
        assert GROUP_CONSTRAINTS in mediator_prompt(scenario.friends, {}, places, travel, cfg)


def result(sid, condition, repetition=1, success=True):
    return dict(scenario_id=sid, condition=condition, repetition=repetition,
        status='success' if success else 'constraint_failure', task_success=success,
        delivered_minimum=.5 if success else 0., delivered_mean=.75 if success else 0.,
        elapsed_seconds=2, verification_revisions=2,
        report=dict(feasible=True, hard_limit_satisfaction=1 if success else .5,
                    per_friend_satisfaction={'a':.5, 'b':1}, fairness=dict(min=.5, gap=.5, jain=.9)),
        usage=dict(logical_calls=4, physical_requests=4, tokens_in=100, tokens_out=20))


def test_raw_quality_does_not_masquerade_as_delivered_quality():
    summary = condition_summary('A', 1, [result('one','A',success=False)])
    assert summary['feasibility'] == 1
    assert summary['task_success_completed'] == 0
    assert summary['hard_limit_satisfaction'] == .5
    assert summary['raw_minimum'] == .5
    assert summary['raw_mean'] == .75
    assert summary['raw_gap'] == .5
    assert summary['raw_jain'] == .9
    assert summary['delivered_minimum'] == 0
    assert summary['verification_revisions'] == 2


def test_cluster_bootstrap_does_not_treat_variants_as_independent():
    diffs = {'a':1, 'b':1, 'c':-1, 'd':-1}
    families = {'a':'one','b':'one','c':'two','d':'two'}
    assert cluster_interval(diffs, families) == (-1., 1., 2)
    assert cluster_interval(diffs, {}) == (None,None,0)
    assert cluster_interval(diffs, dict.fromkeys(diffs,'one')) == (None,None,1)


def test_repetitions_are_averaged_before_paired_differences():
    rows = [result(s,c,r,success=(c=='B')) for s in ('a','b') for c in ('A','B') for r in (1,2,3)]
    jobs = [{k:v for k,v in row.items() if k in ('scenario_id','condition','repetition')} for row in rows]
    pair = next(p for p in paired_summary(rows,jobs,{'a':'one','b':'two'})
                if p['comparison']=='B-A' and p['metric']=='delivered_minimum')
    assert pair['matched_scenarios'] == 2
    assert pair['difference'] == .5
    assert pair['ci95_low'] == pair['ci95_high'] == .5
    incomplete = next(p for p in paired_summary(rows[:-1],jobs,{'a':'one','b':'two'})
                      if p['comparison']=='B-A' and p['metric']=='delivered_minimum')
    assert incomplete['ci95_low'] is None


def test_manifest_tampering_rejected_before_dryrun(tmp_path):
    metadata = json.loads((DATA/'manifest.json').read_text())
    metadata['scenarios'][next(iter(metadata['scenarios']))]['sha256'] = 'incorrect'
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(SystemExit):
        main(['--scenarios',str(DATA/'heldout'),'--dataset','kyoto-final-v1',
              '--dataset-manifest',str(manifest),'--split','heldout',
              '--output',str(tmp_path/'output'),'--dry-run'])
    assert not (tmp_path/'output').exists()
