#!/usr/bin/env python3

from flask import Flask, request
from ipaddress import IPv4Address
import jinja2
import yaml

app = Flask(__name__)


def get_vars():

    with open('../vars.yaml', 'r') as f:
        sw_vars = yaml.safe_load(f)

    vars = {}

    for host_id, params in sw_vars['evpn_peers'].items():
        if request.remote_addr in params['underlay']:
            vars['asn'] = params['asn']
            vars['hostname'] = params['name']
            vars['loopback'] = params['overlay']
            for offset, side in enumerate(['a', 'b']):
                vars[f'localip_{side}'] = params['underlay'][offset]
                vars[f'swip_{side}'] = str(IPv4Address(params['underlay'][offset])-1)

            vars['vlans'] = sw_vars['vlans']
            for vlan_id, vlan in vars['vlans'].items():
                if 'host_base' in vlan.keys():
                    vars['vlans'][vlan_id]['host_ip'] = str(IPv4Address(vlan['host_base']) + host_id)
            
            return vars



@app.route("/frr")
def frr_config():
    return str(get_vars()) + "\n"


@app.route("/nmstate")
def nmstate_config():
    vars = get_vars()

    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
    jinja_env.undefined = jinja2.StrictUndefined
    template = jinja_env.get_template('nmstate.j2')

    return template.render(**vars)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50005)
