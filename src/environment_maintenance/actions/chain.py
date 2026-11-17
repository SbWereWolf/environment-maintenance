"""Legacy EM views backed by the shared planner, coordinator and result store."""
from copy import deepcopy
import json
from command_execution import CommandPlanner, ChainCoordinator, RawOutcome
from .application import ActionExecutor, prepare_action
from .domain import chain_options


def _encode(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')


def prepare_chain(action, parameters, *, input_data, base_dir, interpreters):
    _encode(input_data)
    plan = prepare_action(action, parameters, base_dir=base_dir, interpreters=interpreters)
    for index, (prepared, declared) in enumerate(zip(plan['commands'], action['commands'], strict=True)):
        prepared.update(chain_options(declared, index))
    return plan


def plan_chain(action, parameters, *, input_data, base_dir, interpreters):
    return prepare_chain(action, parameters, input_data=input_data, base_dir=base_dir, interpreters=interpreters)


def execute_prepared(plan, interpreters, runner, input_data=None, on_result=None, chain=False):
    prepared, rows, records = {}, {}, {}
    commands = []
    executor = ActionExecutor(runner)
    aggregate = dict(status='succeeded', data=deepcopy(input_data), commands=[], error=None)
    for index, command in enumerate(plan['commands']):
        if not command.get('enabled', True):
            continue
        identifier = str(index)
        prepared[identifier] = command
        # Legacy background rows do not alter the caller's synchronous decision.
        mode = command.get('mode', 'sync')
        commands.append(dict(id=identifier, argv=command['argv'], order=index,
            execution=mode, on_error=command.get('on_error', 'stop') if mode == 'sync' else 'continue'))
        rows[identifier] = dict(index=index, input_data=None, state='running',
            invocation={key: deepcopy(command[key]) for key in ('argv', 'cwd', 'env')},
            interpreter=deepcopy(command['interpreter']), exit_code=None, stdout=None,
            stderr=None, interpretation=None, error=None, exception=None)
    core_plan, issues = CommandPlanner().compile({'commands': commands})
    if issues:
        raise ValueError(str(issues))

    class ConsumerCoordinator(ChainCoordinator):
        def _run_process(self, spec, stdin, on_chunk, coordinator):
            command = prepared[spec.id]
            invocation = {key: deepcopy(command[key]) for key in ('argv', 'cwd', 'env')}
            if chain:
                invocation['stdin'] = stdin
            try:
                allowed = coordinator.start(lambda: True)
                if allowed is None:
                    raise RuntimeError('Command dispatch stopped')
                raw = runner(deepcopy(invocation))
                records[spec.id] = dict(invocation=invocation, **{
                    key: value for key, value in raw.items() if key != 'invocation'})
                return RawOutcome(spec.argv, raw['exit_code'], raw['stdout'], raw['stderr'])
            except Exception as error:
                if not chain and not isinstance(error, (OSError, ValueError)):
                    raise
                detail = {'type': type(error).__name__, 'message': str(error)}
                records[spec.id] = dict(invocation=invocation, exit_code=None, stdout=b'', stderr=b'',
                    exception=detail, error=f'commands[{spec.id}] launch argv/cwd: {error}')
                return RawOutcome(spec.argv, None, launch_error=detail)

    def interpret(raw, spec):
        record, command = records[spec.id], prepared[spec.id]
        if raw.launch_error:
            record['interpretation'] = None
            return dict(success=False, value=None, error=record['error'])
        config = command['interpreter']
        answer, error, exception = executor._interpret(record, config, interpreters[config['name']])
        record.update(interpretation=answer, error=error, exception=exception)
        if answer is None:
            return dict(success=False, value=None, error=error)
        forwarded = deepcopy(answer)
        if chain and 'next_input' in answer:
            try:
                _encode(answer['next_input'])
            except (ValueError, TypeError) as error:
                record.update(error=f'commands[{spec.id}] next_input: {error}',
                    exception={'type': type(error).__name__, 'message': str(error)})
                forwarded.pop('next_input', None)
                forwarded.update(success=False, error=record['error'])
        return forwarded

    def completed(outcome):
        row = rows[outcome.id]
        if outcome.state == 'dispatch_failed':
            detail = outcome.error
            row.update(error=f'commands[{outcome.id}] dispatch: {detail["message"]}',
                exception={key: detail[key] for key in ('type', 'message')})
        else:
            row.update(records[outcome.id])
        row.update(input_data=deepcopy(outcome.input), state='completed')
        if prepared[outcome.id].get('mode', 'sync') == 'sync' and row['error'] is not None:
            aggregate['status'] = 'failed'
            if aggregate['error'] is None:
                aggregate['error'] = row['error']
        if on_result is not None:
            on_result(deepcopy(row))

    coordinator = ConsumerCoordinator(core_plan, interpreter=interpret)
    run = coordinator.dispatch(input_data, on_result=completed)
    view = run.dispatch_snapshot()
    aggregate['data'] = view['data']
    attempted = {str(row.source_index) for row in coordinator.store.outcomes() if row.state == 'not_attempted'}
    aggregate['commands'] = [rows[key] for key in prepared if key not in attempted]
    if not chain:
        run.wait()
        for row in aggregate['commands']:
            for field in ('index', 'input_data', 'state', 'exception'):
                row.pop(field, None)
        aggregate.pop('data')
    return aggregate


def execute_chain(action, parameters, *, input_data, base_dir, interpreters, run_command=None, on_result=None):
    if run_command is None:
        from .process import run_command
    if not callable(run_command) or (on_result is not None and not callable(on_result)):
        raise ValueError('run_command and on_result must be callable')
    plan = prepare_chain(action, parameters, input_data=input_data, base_dir=base_dir, interpreters=interpreters)
    return execute_prepared(plan, interpreters, run_command, input_data, on_result, chain=True)
