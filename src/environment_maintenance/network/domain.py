"""Declare one network agreement and derive its values without external effects."""
from dataclasses import dataclass
from ipaddress import IPv4Address
import re
from string import Template
from typing import Any


@dataclass(frozen=True)
class OwnerIdentity:
    pid: int
    start_ticks: str


@dataclass(frozen=True)
class PortRequest:
    parameter: str
    host: str
    current_port: int
    owner: OwnerIdentity | None


@dataclass(frozen=True)
class NetworkRequirement:
    id: str
    ports: tuple[PortRequest, ...]
    addresses: dict[str, str]


class NetworkFailure(Exception):
    def __init__(self, code: str, context: str, cause: str):
        super().__init__(cause)
        self.code, self.context, self.cause = code, context, cause


def _name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(Template.idpattern, value, re.ASCII | re.IGNORECASE):
        raise ValueError(f"{context}: expected a Template identifier")
    return value


def _port(declaration: Any, parameters: dict, context: str) -> PortRequest:
    if not isinstance(declaration, dict):
        raise ValueError(f"{context}: expected an object")
    name = _name(declaration.get('parameter'), f'{context}.parameter')
    if name not in parameters:
        raise ValueError(f"{context}.{name}: required existing parameter is missing")
    port = parameters[name]
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError(f"{context}.{name}: expected integer in range 0..65535")
    host = declaration.get('host')
    try:
        if not isinstance(host, str):
            raise ValueError()
        IPv4Address(host)
    except ValueError as exc:
        raise ValueError(f"{context}.host: expected numeric IPv4 address") from exc
    owner = None
    if 'owner' in declaration:
        value = declaration['owner']
        label = f'{context}.{name}.owner'
        if not isinstance(value, dict) or 'pid' not in value or 'start_ticks' not in value:
            raise ValueError(f"{label}: expected object with pid and start_ticks")
        if type(value['pid']) is not int or value['pid'] <= 0:
            raise ValueError(f"{label}.pid: expected positive integer")
        ticks = value['start_ticks']
        if not isinstance(ticks, str) or not re.fullmatch(r'0|[1-9][0-9]*', ticks):
            raise ValueError(f"{label}.start_ticks: expected canonical ASCII decimal string")
        if port == 0:
            raise ValueError(f"{label}: owner requires positive existing {name} port")
        owner = OwnerIdentity(value['pid'], ticks)
    return PortRequest(name, host, port, owner)


def plan_network(requirements: list[dict], parameters: dict) -> tuple[NetworkRequirement, ...]:
    plans = []
    port_names, outputs = set(), set()
    for requirement in requirements:
        context = f"adjust requirement {requirement['id']} network"
        network = requirement['network']
        if not isinstance(network, dict):
            raise ValueError(f"{context}: expected object")
        declarations = network.get('ports')
        if not isinstance(declarations, list) or not declarations:
            raise ValueError(f"{context}.ports: expected nonempty array")
        ports = []
        for index, declaration in enumerate(declarations):
            request = _port(declaration, parameters, f'{context}.ports[{index}]')
            if request.parameter in port_names:
                raise ValueError(f"{context}: duplicate port {request.parameter}; declare unique keys")
            port_names.add(request.parameter)
            ports.append(request)
        addresses = network.get('addresses')
        if not isinstance(addresses, dict):
            raise ValueError(f"{context}.addresses: expected object")
        for key, recipe in addresses.items():
            _name(key, f'{context}.addresses')
            if key in outputs:
                raise ValueError(f"{context}: duplicate address output {key}; declare unique keys")
            outputs.add(key)
            if not isinstance(recipe, str):
                raise ValueError(f"{context}.addresses.{key}: expected string recipe")
        plans.append(NetworkRequirement(requirement['id'], tuple(ports), dict(addresses)))
    overlap = port_names & outputs
    if overlap:
        raise ValueError(f"adjust network: port/output overlap {', '.join(sorted(overlap))}")
    for plan in plans:
        for key, recipe in plan.addresses.items():
            context = f'adjust requirement {plan.id} network.addresses.{key}'
            if key in parameters and not isinstance(parameters[key], str):
                raise ValueError(f"{context}: existing address must be a string")
            template = Template(recipe)
            if not template.is_valid():
                raise ValueError(f"{context}: invalid Template syntax; correct the recipe")
            for name in template.get_identifiers():
                if name in outputs:
                    raise ValueError(f"{context}: derived output reference {name}; use input/port values")
                if name not in parameters:
                    raise ValueError(f"{context}: unknown parameter {name}; provide the missing input")
    return tuple(plans)


def derive_values(plans, parameters, assigned_ports):
    values = dict(parameters)
    values.update(assigned_ports)
    results = []
    for plan in plans:
        produced = {port.parameter: assigned_ports[port.parameter] for port in plan.ports}
        produced.update({key: Template(recipe).substitute(values)
                         for key, recipe in plan.addresses.items()})
        changed = any(key not in parameters or parameters[key] != value
                      for key, value in produced.items())
        values.update(produced)
        results.append(dict(ports={port.parameter: assigned_ports[port.parameter] for port in plan.ports},
                            addresses=list(plan.addresses), changed=changed, error_code=None))
    return values, results
