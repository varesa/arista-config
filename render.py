#!/usr/bin/env python

import jinja2
import itertools
import yaml

with open('vars.yaml', 'r') as f:
    vars = yaml.safe_load(f)
with open('secrets.yaml', 'r') as f:
    vars.update(yaml.safe_load(f))


def if_sort_key(interface: tuple):
    interface_name = interface[0]
    if interface_name.lower().startswith('ethernet'):
        type = 0
        numbers = interface_name[8:]
    else:
        assert False, f"Unsupported interface_name type {interface_name}"
    if '/' in numbers:
        num_int, num_sub = numbers.split('/')
        return (type, int(num_int), int(num_sub))
    else:
        return (type, int(numbers), 0)


def if_sort(interfaces: dict):
    return sorted(interfaces.items(), key=if_sort_key)


jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
jinja_env.filters['if_sort'] = if_sort
jinja_env.undefined = jinja2.StrictUndefined
template = jinja_env.get_template('template.j2')


for int_i, int_sub in itertools.product(range(1, 25), range(1, 5)):
    interface = f'Ethernet{int_i}/{int_sub}'
    if interface not in vars['interfaces'].keys():
        vars['interfaces'][interface] = {"shutdown": True}

for int_i in range(25, 33):
    interface = f'Ethernet{int_i}'
    if interface not in vars['interfaces'].keys():
        vars['interfaces'][interface] = {"shutdown": True}

for line in template.render(**vars).split('\n'):
    if line.strip() != "":
        print(line)
