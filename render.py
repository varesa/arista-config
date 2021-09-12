#!/usr/bin/env python

import jinja2
import itertools
import yaml
import sys
import ipaddress

with open('vars.yaml', 'r') as f:
    vars = yaml.safe_load(f)
with open('secrets.yaml', 'r') as f:
    vars.update(yaml.safe_load(f))

def ip_address(cidr):
    return cidr.split('/')[0]

def ip_mask(cidr):
    return str(ipaddress.IPv4Interface(cidr).netmask)

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
jinja_env.filters['ip_address'] = ip_address
jinja_env.filters['ip_mask'] = ip_mask
jinja_env.filters['if_sort'] = if_sort
jinja_env.undefined = jinja2.StrictUndefined
template = jinja_env.get_template('template.j2')

vars['dhcp_pools'] = []
for interface_name, interface in vars['interfaces'].items():
    if interface.get('dhcp', False):
        network = ipaddress.IPv4Interface(interface['address']).network
        peer = ipaddress.IPv4Interface(interface['address']).ip + 1
        vars['dhcp_pools'].append({"network": str(network), "address": str(peer)})

for int_i, int_sub in itertools.product(range(1,25), range(1,5)):
    interface = f'Ethernet{int_i}/{int_sub}'
    if interface not in vars['interfaces'].keys():
        vars['interfaces'][interface] = { "shutdown": True }

for int_i in range(25,33):
    interface = f'Ethernet{int_i}'
    if interface not in vars['interfaces'].keys():
        vars['interfaces'][interface] = { "shutdown": True }

underlay_peers = []
for id, peer in vars['evpn_peers'].items():
    for address in peer['underlay']:
        underlay_peers.append({"address": address, "asn": peer['asn']})
vars['underlay_peers'] = sorted(underlay_peers, key=lambda peer: [int(octet) for octet in peer['address'].split('.')])

for vlan_id, vlan in vars['vlans'].items():
    vars['vlans'][vlan_id]['id_s'] = str(vlan_id)

for line in template.render(**vars).split('\n'):
    if line.strip() != "":
        print(line)

