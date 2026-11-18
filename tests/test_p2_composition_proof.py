"""O observador não pode aprovar eventos diferentes dos frames e da referência."""
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

SPEC=spec_from_file_location('p2_composition_proof',Path(__file__).parents[1]/'composicao-ver1/p2/provar.py')
proof=module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def scenario():
    rows=[];samples=[];events=[]
    for index in range(3):
        row=dict(source_id='synthetic',session_id='session',frame_index=index+1,detection_id=0,
                 captured_at='2026-11-06T12:00:00.000Z',bbox=[0,0,224,224])
        expected=dict(result='ANOMALY',defect_class=None,confidence=.9,similarity=.1)
        event=dict(message_id=str(index),source_id=row['source_id'],session_id=row['session_id'],
            sequence=index,captured_at=row['captured_at'],occurred_at='2026-11-06T12:00:01.000Z',
            published_at='2026-11-06T12:00:02.000Z',schema='ods.industria.defeito_classificado',
            schema_version='2.0',artifact_version='engine-fp32',payload=dict(
                frame_index=row['frame_index'],detection_id=0,bbox=row['bbox'],**expected))
        rows.append(row);samples.append({'expected':expected});events.append(event)
    return rows,samples,events


def test_equivalent_reference_is_accepted_with_fp32_tolerance():
    rows,samples,events=scenario()
    events[0]['payload']['similarity']+=1e-6
    proof.check_events(rows,samples,events,'engine-fp32')


@pytest.mark.parametrize('case',['wrong_engine','duplicate_identity','wrong_prediction','wrong_frame','wrong_sequence','wrong_time','missing_event'])
def test_inconsistent_proof_is_rejected(case):
    rows,samples,events=scenario();events=deepcopy(events)
    if case=='wrong_engine':events[0]['artifact_version']='another-engine'
    elif case=='duplicate_identity':events[1]['message_id']=events[0]['message_id']
    elif case=='wrong_prediction':events[0]['payload']['result']='CONFORMING'
    elif case=='wrong_frame':events[0]['payload']['bbox']=[1,1,224,224]
    elif case=='wrong_sequence':events[1]['sequence']=99
    elif case=='wrong_time':events[0]['occurred_at']='2026-11-05T12:00:00.000Z'
    else:events.pop()
    with pytest.raises(AssertionError):proof.check_events(rows,samples,events,'engine-fp32')
