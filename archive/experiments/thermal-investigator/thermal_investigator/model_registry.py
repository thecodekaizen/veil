"""Allowlisted executable models. Unknown structures never become code."""
from .physical import execute_model
from .nonlinear import execute_quadratic


def execute_candidate(value,commands,ambient_c=22.):
    if not isinstance(value,dict) or not isinstance(value.get('specification'),dict):
        raise ValueError('Missing bounded model specification')
    kind=value['specification'].get('type')
    if kind=='two_node_thermal':return execute_model(value,commands,ambient_c)
    if kind=='two_node_quadratic_loss':return execute_quadratic(value,commands,ambient_c)
    raise ValueError('Unsupported model structure')
