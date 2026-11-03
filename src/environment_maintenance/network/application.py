"""Hold the entire selected agreement through its single publication boundary."""
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from pathlib import Path

from ..configuration.application import DocumentWriter
from .domain import NetworkFailure, PortRequest, derive_values, plan_network


ReservePort = Callable[[str, int], AbstractContextManager[int]]
ConfirmOwner = Callable[[PortRequest], None]


class NetworkAdjustment:
    def __init__(self, reserve_port: ReservePort, confirm_owner: ConfirmOwner,
                 write_document: DocumentWriter):
        self._reserve_port = reserve_port
        self._confirm_owner = confirm_owner
        self._write_document = write_document

    def adjust(self, requirements, parameters, *, parameters_path: Path, retry_command: str):
        plans = plan_network(requirements, parameters)
        try:
            with ExitStack() as reservations:
                assigned = {}
                for plan in plans:
                    for request in plan.ports:
                        if request.owner is not None:
                            self._confirm_owner(request)
                            assigned[request.parameter] = request.current_port
                        else:
                            try:
                                assigned[request.parameter] = reservations.enter_context(
                                    self._reserve_port(request.host, request.current_port))
                            except OSError as exc:
                                raise NetworkFailure('allocation_failed', request.parameter,
                                    f'{request.host}:{request.current_port}: {exc}') from exc
                values, results = derive_values(plans, parameters, assigned)
                if any(result['changed'] for result in results):
                    try:
                        self._write_document(parameters_path, values)
                    except (ValueError, OSError) as exc:
                        raise NetworkFailure('write_failed', str(parameters_path), str(exc)) from exc
        except NetworkFailure as exc:
            return self._failure(plans, exc, retry_command)
        records = [dict(id=plan.id, result=dict(status='succeeded', commands=[], error=None,
                                               network=result))
                   for plan, result in zip(plans, results)]
        return dict(operation='adjust', status='succeeded', requirements=records, error=None)

    @staticmethod
    def _failure(plans, failure, retry_command):
        remedies = {
            'allocation_failed': 'Восстановите доступность локального адреса и ресурсов сокетов.',
            'ownership_mismatch': 'Обновите owner по фактическому работающему экземпляру и его listener.',
            'ownership_unavailable': 'Восстановите доступ к данным процесса и его сокетов.',
            'write_failed': 'Восстановите доступ к выбранному файлу и каталогу для записи.',
        }
        error = (f'adjust network {failure.context}: {failure.cause}. '
                 f'{remedies[failure.code]} Выполните: {retry_command}')
        records = [dict(id=plan.id, result=dict(status='failed', commands=[], error=error,
                       network=dict(ports={}, addresses=[], changed=False, error_code=failure.code)))
                   for plan in plans]
        return dict(operation='adjust', status='failed', requirements=records, error=error)
