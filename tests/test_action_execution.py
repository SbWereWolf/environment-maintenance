"""Public action contract: real processes, independent data, preserved raw bytes."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

import environment_maintenance as public_api


FIXTURES = Path(__file__).parent / 'fixtures' / 'action-execution'
FUNCTIONS = ('plan_action', 'execute_action')


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def payload(name):
    path = FIXTURES / name
    return bytes.fromhex(path.read_text(encoding='utf-8')) if path.suffix == '.hex' else path.read_bytes()


def assert_json_value(actual, expected):
    # Preserve JSON types; ordinary equality equates False with 0 and True with 1.
    assert json.dumps(actual, ensure_ascii=False, sort_keys=True) == json.dumps(
        expected, ensure_ascii=False, sort_keys=True
    )


def api(name):
    function = getattr(public_api, name, None)
    assert callable(function), f'Missing required public action API: {name}'
    return function


class ExitInterpreter:
    """A test-owned external interpreter whose accepted codes come from options."""
    def __init__(self):
        self.calls = []

    def interpret(self, result, options):
        self.calls.append((deepcopy(result), deepcopy(options)))
        success = result['exit_code'] in options['accept']
        return dict(success=success, value=options['tag'],
                    error=None if success else 'exit code rejected', source='exit')


class JsonInterpreter:
    """A different ordinary consumer of the same raw-result interface."""
    def __init__(self):
        self.calls = []

    def interpret(self, result, options):
        self.calls.append((deepcopy(result), deepcopy(options)))
        data = json.loads(result['stdout'])
        success = data['state'] == options['expected']
        return dict(success=success, value=data['number'],
                    error=None if success else 'state rejected', source='json')


class BrokenInterpreter:
    def __init__(self, malformed):
        self.malformed = malformed

    def interpret(self, result, options):
        if self.malformed:
            return dict(success='yes', value=None, error=None)
        raise ValueError('specific interpreter refusal')


class AnswerInterpreter:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def interpret(self, result, options):
        self.calls.append((deepcopy(result), deepcopy(options)))
        return deepcopy(self.answer)


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    root = tmp_path / 'workspace with spaces'
    (root / 'work').mkdir(parents=True)
    (root / 'other').mkdir()
    parameters = fixture('parameters.json')
    parameters['python'] = sys.executable
    parameters['probe'] = str(FIXTURES / 'probe.py')
    parameters['events'] = str(root / 'events.jsonl')
    parameters['stdout'] = str(FIXTURES / 'stdout.txt')
    parameters['stderr'] = str(FIXTURES / 'stderr.txt')
    monkeypatch.setenv('ENV2_HOST_ONLY', 'host value must not be inherited')
    return SimpleNamespace(root=root, events=root / 'events.jsonl',
                           action=fixture('action.json'), parameters=parameters,
                           interpreters={'exit': ExitInterpreter(), 'json': JsonInterpreter()})


def invoke(name, scenario, *, action=None, parameters=None, interpreters=None):
    return api(name)(scenario.action if action is None else action,
                     scenario.parameters if parameters is None else parameters,
                     base_dir=scenario.root,
                     interpreters=scenario.interpreters if interpreters is None else interpreters)


def expected_invocation(scenario, *, token='first', stdout='stdout.txt',
                        stderr='stderr.txt', code='0', cwd='work', visible='selected',
                        arguments=None):
    expected = fixture('expected-invocation.json')
    expected['argv'][0] = sys.executable
    expected['argv'][1] = str(FIXTURES / 'probe.py')
    expected['argv'][2] = str(scenario.events)
    expected['argv'][3] = token
    expected['argv'][4] = str(FIXTURES / stdout)
    expected['argv'][5] = str(FIXTURES / stderr)
    expected['argv'][6] = code
    if arguments is not None:
        expected['argv'][7:] = arguments
    expected['cwd'] = str(scenario.root / cwd)
    expected['env']['VISIBLE'] = visible
    return expected


def assert_invocation(actual, expected):
    for field in ('argv', 'cwd', 'env'):
        assert actual[field] == expected[field]


def events(scenario):
    assert scenario.events.is_file(), 'Declared external command did not create its marker'
    return [json.loads(line) for line in scenario.events.read_text(encoding='utf-8').splitlines()]


def assert_context(error, *references):
    message = str(error).casefold()
    assert any(reference and re.search(r'(?<!\w)' + re.escape(reference.casefold()) + r'(?!\w)', message)
               for reference in references), f'Diagnostic lacks input-related context: {error!s}'


def command(scenario, *, token, code='0', stdout='stdout.txt', cwd='work', visible='selected', interpreter='exit'):
    result = deepcopy(scenario.action['commands'][0])
    result['argv'][3] = token
    result['argv'][4] = str(FIXTURES / stdout)
    result['argv'][6] = code
    result['cwd'] = cwd
    result['env']['VISIBLE'] = visible
    result['interpreter']['name'] = interpreter
    return result


def assert_raw(record, expected, *, code=0, stdout='stdout.txt', stderr='stderr.txt'):
    assert_invocation(record['invocation'], expected)
    assert type(record['exit_code']) is int and record['exit_code'] == code
    assert type(record['stdout']) is bytes and record['stdout'] == payload(stdout)
    assert type(record['stderr']) is bytes and record['stderr'] == payload(stderr)


@pytest.mark.parametrize('name', FUNCTIONS)
def test_public_action_function_exists(name):
    api(name)


@pytest.mark.parametrize('absolute', [False, True])
def test_plan_preserves_environment_inputs_and_opaque_options(scenario, absolute):
    if absolute:
        scenario.parameters['cwd'] = str(scenario.root / 'work')
    before = deepcopy((scenario.action, scenario.parameters))
    plan = invoke('plan_action', scenario)
    assert len(plan['commands']) == 1
    assert_invocation(plan['commands'][0], expected_invocation(scenario))
    assert_json_value(plan['commands'][0]['interpreter'], before[0]['commands'][0]['interpreter'])
    assert_json_value((scenario.action, scenario.parameters), before)
    assert not scenario.events.exists()
    assert all(item.calls == [] for item in scenario.interpreters.values())
    assert sorted(p.name for p in scenario.root.iterdir()) == ['other', 'work']


@pytest.mark.parametrize('absolute', [False, True])
def test_plan_accepts_future_resources_prepared_by_an_earlier_command(scenario, absolute):
    executable = scenario.root / 'future-python'
    directory = scenario.root / 'future-work'
    preparation = payload('prepare-resource.py').decode('utf-8').removesuffix('\n')
    action = deepcopy(scenario.action)
    action['commands'][0]['argv'] = ['${python}', '-c', preparation, '${future_executable}', '${future_directory}']
    future = command(scenario, token='future', cwd='${future_cwd}')
    future['argv'][0] = '${future_executable}'
    action['commands'].append(future)
    parameters = deepcopy(scenario.parameters)
    parameters.update(future_executable=str(executable), future_directory=str(directory),
                      future_cwd=str(directory) if absolute else 'future-work')
    before = deepcopy((action, parameters))
    assert not executable.exists() and not directory.exists()
    plan = invoke('plan_action', scenario, action=action, parameters=parameters)
    assert len(plan['commands']) == 2
    first = expected_invocation(scenario)
    first['argv'] = [sys.executable, '-c', preparation, str(executable), str(directory)]
    second = expected_invocation(scenario, token='future', cwd='future-work')
    second['argv'][0] = str(executable)
    for actual, expected in zip(plan['commands'], (first, second), strict=True):
        assert_invocation(actual, expected)
        assert_json_value(actual['interpreter'], action['commands'][0]['interpreter'])
    assert_json_value((action, parameters), before)
    assert not executable.exists() and not directory.exists() and not scenario.events.exists()
    assert sorted(p.name for p in scenario.root.iterdir()) == ['other', 'work']
    assert all(item.calls == [] for item in scenario.interpreters.values())


@pytest.mark.parametrize('name', FUNCTIONS)
def test_unused_parameters_are_allowed_and_preserved(scenario, name):
    parameters = deepcopy(scenario.parameters)
    parameters.update(unused='${unbound_unused}', unused_number=42, unused_flag=False)
    before = deepcopy(parameters)
    result = invoke(name, scenario, parameters=parameters)
    record = result['commands'][0]
    assert_invocation(record if name == 'plan_action' else record['invocation'], expected_invocation(scenario))
    assert_json_value(parameters, before)
    if name == 'plan_action':
        assert not scenario.events.exists()
        assert all(item.calls == [] for item in scenario.interpreters.values())
    else:
        assert result['status'] == 'succeeded' and result['error'] is None
        assert [row['token'] for row in events(scenario)] == ['first']


@pytest.mark.parametrize(('template', 'value', 'expected'), [
    ('${arg}', 'two words', 'two words'),
    ('${arg}', '', ''),
    ('${arg}', 'Кириллица 😀', 'Кириллица 😀'),
    ('$arg-tail', 'chosen', 'chosen-tail'),
    ('$${arg}', 'unused', '${arg}'),
    ('${arg}', '${unbound}', '${unbound}'),
    ('prefix:${arg}:$$', 'x y', 'prefix:x y:$'),
])
def test_standard_one_pass_substitution_preserves_argument_boundaries(scenario, template, value, expected):
    scenario.action['commands'][0]['argv'][7] = template
    scenario.parameters['arg'] = value
    plan = invoke('plan_action', scenario)
    assert_invocation(plan['commands'][0], expected_invocation(scenario, arguments=[expected]))
    assert not scenario.events.exists()


@pytest.mark.parametrize(('value', 'expected'), [('text', 'text'), (5432, '5432'), (1.5, '1.5'), (False, 'False')])
def test_standard_scalar_conversion_in_environment(scenario, value, expected):
    scenario.parameters['value'] = value
    plan = invoke('plan_action', scenario)
    assert_invocation(plan['commands'][0], expected_invocation(scenario, visible=expected))


def test_real_chain_uses_order_contexts_parameters_and_each_configured_interpreter(scenario):
    action = deepcopy(scenario.action)
    action['commands'].append(command(scenario, token='second', stdout='state.json', cwd='other',
                                      visible='second-env', interpreter='json'))
    before = deepcopy((action, scenario.parameters))
    plan = invoke('plan_action', scenario, action=action)
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert len(result['commands']) == 2
    observations = events(scenario)
    assert [item['token'] for item in observations] == ['first', 'second']
    expected = fixture('expected-observation.json')
    first = observations[0].copy()
    assert first.pop('cwd') == str(scenario.root / 'work')
    assert first == expected
    second = observations[1].copy()
    assert second.pop('cwd') == str(scenario.root / 'other')
    expected['token'] = 'second'
    expected['visible'] = 'second-env'
    assert second == expected
    assert_raw(result['commands'][0], expected_invocation(scenario))
    assert_raw(result['commands'][1], expected_invocation(scenario, token='second', stdout='state.json',
                                                        cwd='other', visible='second-env'), stdout='state.json')
    for index, kind in enumerate(('exit', 'json')):
        record = result['commands'][index]
        assert_json_value(record['interpretation'], fixture('expected-interpretations.json')[kind])
        assert_json_value(record['interpreter'], plan['commands'][index]['interpreter'])
        assert_invocation(record['invocation'], plan['commands'][index])
        assert record['error'] is None
        calls = scenario.interpreters[kind].calls
        assert len(calls) == 1
        raw, options = calls[0]
        assert_raw(raw, record['invocation'], stdout='stdout.txt' if index == 0 else 'state.json')
        assert_json_value(options, action['commands'][index]['interpreter']['options'])
    assert_json_value((action, scenario.parameters), before)


@pytest.mark.parametrize(('stdout', 'stderr'), [
    ('empty.txt', 'empty.txt'), ('stdout.txt', 'stderr.txt'),
    ('state.json', 'binary.hex'), ('binary.hex', 'state.json'),
    ('large-stdout.txt', 'large-stderr.txt'),
])
def test_full_distinct_raw_streams_reach_caller_and_interpreter(scenario, stdout, stderr):
    scenario.parameters['stdout'] = str(FIXTURES / stdout)
    scenario.parameters['stderr'] = str(FIXTURES / stderr)
    result = invoke('execute_action', scenario)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert len(result['commands']) == 1
    record = result['commands'][0]
    expected = expected_invocation(scenario, stdout=stdout, stderr=stderr)
    assert_raw(record, expected, stdout=stdout, stderr=stderr)
    assert_raw(scenario.interpreters['exit'].calls[0][0], expected, stdout=stdout, stderr=stderr)
    assert [item['token'] for item in events(scenario)] == ['first']


def test_same_configured_name_can_receive_another_interface_implementation(scenario):
    scenario.parameters['stdout'] = str(FIXTURES / 'state.json')
    first = invoke('execute_action', scenario, interpreters={'exit': ExitInterpreter()})
    second = invoke('execute_action', scenario, interpreters={'exit': JsonInterpreter()})
    assert first['status'] == second['status'] == 'succeeded'
    assert_json_value(first['commands'][0]['interpretation'], fixture('expected-interpretations.json')['exit'])
    assert_json_value(second['commands'][0]['interpretation'], fixture('expected-interpretations.json')['json'])
    assert first['commands'][0]['stdout'] == second['commands'][0]['stdout'] == payload('state.json')
    assert [row['token'] for row in events(scenario)] == ['first', 'first']


def test_interpreter_can_explicitly_accept_nonzero_process_code(scenario):
    second = command(scenario, token='second')
    scenario.action['commands'][0]['interpreter']['options']['accept'] = [1]
    scenario.parameters['code'] = 1
    scenario.action['commands'].append(second)
    result = invoke('execute_action', scenario)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert len(result['commands']) == 2
    assert_raw(result['commands'][0], expected_invocation(scenario, code='1'), code=1)
    assert result['commands'][0]['interpretation']['success'] is True
    assert [row['token'] for row in events(scenario)] == ['first', 'second']


@pytest.mark.parametrize(('failure_at', 'reject_zero'), [(0, False), (1, False), (1, True)])
def test_chain_stops_on_interpreted_failure_with_complete_prior_results(scenario, failure_at, reject_zero):
    action = deepcopy(scenario.action)
    action['commands'].append(command(scenario, token='second'))
    action['commands'].append(command(scenario, token='never'))
    failed = action['commands'][failure_at]
    if reject_zero:
        failed['interpreter']['options']['accept'] = []
    else:
        failed['argv'][6] = '2'
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'failed'
    assert len(result['commands']) == failure_at + 1
    assert [row['token'] for row in events(scenario)] == (['first'] if failure_at == 0 else ['first', 'second'])
    for index, record in enumerate(result['commands']):
        code = 2 if index == failure_at and not reject_zero else 0
        token = 'first' if index == 0 else 'second'
        assert_raw(record, expected_invocation(scenario, token=token, code=str(code)), code=code)
        assert record['interpretation']['success'] is (index != failure_at)
    error = result['commands'][-1]['error']
    assert error and result['error'] == error
    assert_context(error, 'exit', 'interpreter', 'interpretation',
                   'first' if failure_at == 0 else 'second')
    assert len(scenario.interpreters['exit'].calls) == failure_at + 1


@pytest.mark.parametrize('boundary', ['executable', 'cwd'])
def test_launch_failure_retains_prior_effects_and_records_the_attempt(scenario, boundary):
    action = deepcopy(scenario.action)
    bad = command(scenario, token='not-started')
    if boundary == 'executable':
        bad['argv'][0] = str(scenario.root / 'absent-executable')
        reference = 'absent-executable'
    else:
        bad['cwd'] = 'absent-directory'
        reference = 'absent-directory'
    action['commands'].extend([bad, command(scenario, token='never')])
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'failed' and len(result['commands']) == 2
    assert_raw(result['commands'][0], expected_invocation(scenario))
    failed = result['commands'][1]
    assert failed['exit_code'] is None
    assert failed['stdout'] == failed['stderr'] == b''
    assert failed['interpretation'] is None
    assert_context(failed['error'], reference, 'argv' if boundary == 'executable' else 'cwd')
    assert result['error'] == failed['error']
    assert [row['token'] for row in events(scenario)] == ['first']
    assert len(scenario.interpreters['exit'].calls) == 1


@pytest.mark.parametrize('malformed', [False, True])
def test_interpretation_failure_retains_all_raw_data_and_stops(scenario, malformed):
    scenario.interpreters['broken'] = BrokenInterpreter(malformed)
    action = deepcopy(scenario.action)
    action['commands'].append(command(scenario, token='second', interpreter='broken'))
    action['commands'].append(command(scenario, token='never'))
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'failed' and len(result['commands']) == 2
    assert_raw(result['commands'][0], expected_invocation(scenario))
    failed = result['commands'][1]
    assert_raw(failed, expected_invocation(scenario, token='second'))
    assert_context(failed['error'], 'broken', 'second', 'interpreter', 'interpretation', 'success')
    assert result['error'] == failed['error']
    assert [row['token'] for row in events(scenario)] == ['first', 'second']


@pytest.mark.parametrize('case', fixture('invalid-interpretations.json'), ids=lambda row: row['name'])
def test_invalid_interpreter_answer_retains_raw_results_and_stops(scenario, case):
    answer = AnswerInterpreter(case['answer'])
    scenario.interpreters['answer'] = answer
    action = deepcopy(scenario.action)
    action['commands'].extend([command(scenario, token='second', interpreter='answer'),
                               command(scenario, token='never')])
    before = deepcopy((action, scenario.parameters, case['answer']))
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'failed' and len(result['commands']) == 2
    assert_raw(result['commands'][0], expected_invocation(scenario))
    assert_json_value(result['commands'][0]['interpretation'], fixture('expected-interpretations.json')['exit'])
    failed = result['commands'][1]
    assert_raw(failed, expected_invocation(scenario, token='second'))
    assert failed['error'] and result['error'] == failed['error']
    assert_context(failed['error'], 'answer', 'interpreter', 'interpretation', *case['references'])
    assert [row['token'] for row in events(scenario)] == ['first', 'second']
    assert len(answer.calls) == len(scenario.interpreters['exit'].calls) == 1
    raw, options = answer.calls[0]
    assert_raw(raw, expected_invocation(scenario, token='second'))
    assert_json_value(options, action['commands'][1]['interpreter']['options'])
    assert_json_value((action, scenario.parameters, case['answer']), before)


def test_opaque_interpreter_value_and_extra_fields_are_preserved(scenario):
    answer = fixture('opaque-interpretation.json')
    scenario.interpreters['answer'] = AnswerInterpreter(answer)
    action = deepcopy(scenario.action)
    action['commands'][0]['interpreter']['name'] = 'answer'
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert len(result['commands']) == 1
    assert_raw(result['commands'][0], expected_invocation(scenario))
    assert_json_value(result['commands'][0]['interpretation'], answer)
    assert_json_value(scenario.interpreters['answer'].answer, answer)
    assert [row['token'] for row in events(scenario)] == ['first']


@pytest.mark.parametrize('name', FUNCTIONS)
@pytest.mark.parametrize('case', fixture('invalid-api-inputs.json'), ids=lambda row: row['name'])
def test_invalid_api_inputs_fail_before_effects_with_context(scenario, name, case):
    function = api(name)
    action = deepcopy(scenario.action)
    parameters = deepcopy(scenario.parameters)
    base_dir = scenario.root
    interpreters = scenario.interpreters.copy()
    field = case['field']
    if field == 'action':
        action = deepcopy(case['value'])
    elif field == 'parameters':
        parameters = deepcopy(case['value'])
    elif field == 'used_parameter':
        parameters['arg'] = deepcopy(case['value'])
    elif field == 'base_dir':
        base_dir = case['value']
    elif field == 'interpreters':
        interpreters = deepcopy(case['value'])
    else:
        assert field == 'selected_interpreter'
        interpreters['exit'] = deepcopy(case['value'])
    before = deepcopy((action, parameters, base_dir))
    registry_before = ({key: value if hasattr(value, 'interpret') else deepcopy(value)
                        for key, value in interpreters.items()}
                       if isinstance(interpreters, dict) else deepcopy(interpreters))
    with pytest.raises(ValueError) as error:
        function(action, parameters, base_dir=base_dir, interpreters=interpreters)
    assert_context(error.value, *case['references'])
    assert_json_value((action, parameters), before[:2])
    assert base_dir == before[2]
    assert interpreters == registry_before
    assert not scenario.events.exists()
    assert sorted(p.name for p in scenario.root.iterdir()) == ['other', 'work']
    assert all(item.calls == [] for item in scenario.interpreters.values())


@pytest.mark.parametrize('name', FUNCTIONS)
@pytest.mark.parametrize('case', fixture('invalid-actions.json'), ids=lambda row: row['name'])
def test_invalid_declared_fields_fail_before_execution_with_context(scenario, name, case):
    function = api(name)
    before = deepcopy(case['action'])
    with pytest.raises(ValueError) as error:
        function(case['action'], scenario.parameters, base_dir=scenario.root, interpreters=scenario.interpreters)
    assert_context(error.value, *case['references'], 'commands[0]')
    assert_json_value(case['action'], before)
    assert not scenario.events.exists()
    assert all(item.calls == [] for item in scenario.interpreters.values())


@pytest.mark.parametrize('name', FUNCTIONS)
@pytest.mark.parametrize(('template', 'reference'), [('${unbound_argument}', 'unbound_argument'), ('$', 'argv')])
def test_missing_parameter_or_invalid_template_prevents_every_command(scenario, name, template, reference):
    action = deepcopy(scenario.action)
    bad = command(scenario, token='never')
    bad['argv'][7] = template
    action['commands'].append(bad)
    function = api(name)
    with pytest.raises(ValueError) as error:
        function(action, scenario.parameters, base_dir=scenario.root, interpreters=scenario.interpreters)
    assert_context(error.value, reference, 'argv', 'commands[1]')
    assert not scenario.events.exists()
    assert all(item.calls == [] for item in scenario.interpreters.values())


@pytest.mark.parametrize('name', FUNCTIONS)
def test_unknown_interpreter_prevents_the_complete_chain(scenario, name):
    action = deepcopy(scenario.action)
    action['commands'].append(command(scenario, token='never', interpreter='unavailable_handler'))
    function = api(name)
    with pytest.raises(ValueError) as error:
        function(action, scenario.parameters, base_dir=scenario.root, interpreters=scenario.interpreters)
    assert_context(error.value, 'unavailable_handler', 'interpreter', 'commands[1]')
    assert not scenario.events.exists()
    assert all(item.calls == [] for item in scenario.interpreters.values())


def test_action_read_through_configuration_api_executes_without_changing_files(scenario):
    main = scenario.root / 'app.json'
    selected = scenario.root / 'actions.json'
    main.write_text(json.dumps({'operations': {'infra': 'actions.json'}}), encoding='utf-8')
    selected.write_bytes((FIXTURES / 'configuration.json').read_bytes())
    before = (main.read_bytes(), selected.read_bytes())
    action = public_api.read_requirements(main, 'infra', ['selected-resource'])[0]
    result = invoke('execute_action', scenario, action=action)
    assert result['status'] == 'succeeded'
    assert_raw(result['commands'][0], expected_invocation(scenario))
    assert (main.read_bytes(), selected.read_bytes()) == before
    assert [row['token'] for row in events(scenario)] == ['first']
