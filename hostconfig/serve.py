#!/usr/bin/env python3

from flask import Flask, request, send_file
from ipaddress import IPv4Address
import io
import jinja2
import os
import sys
import tarfile
import tempfile
import yaml

app = Flask(__name__)
basepath = os.path.dirname(sys.argv[0])


def get_peer(sw_vars: dict, peer_ip: str) -> (int, dict):
    """
    Filter the list of configured peers for the given IP address.

    Returns the ID of the peer in the dict and parameters under that ID.
    """

    for host_id, params in sw_vars['evpn_peers'].items():
        if peer_ip in params['underlay']:
            return host_id, params
    
    return None


def get_vars() -> dict:
    """
    Generate a view of the configuration variables specific to the 
    client that connected.

    Requires active Flask request context
    """

    with open(os.path.join(basepath, '../vars.yaml'), 'r') as f:
        sw_vars = yaml.safe_load(f)

    peer_ip = request.remote_addr
    peer_id, peer_params = get_peer(sw_vars, peer_ip)

    vars = {}

    # Basic details
    vars['asn'] = peer_params['asn']
    vars['hostname'] = peer_params['name']
    vars['loopback'] = peer_params['overlay']

    # Link networks
    for offset, side in enumerate(['a', 'b']):
        vars[f'localip_{side}'] = peer_params['underlay'][offset]
        vars[f'swip_{side}'] = str(IPv4Address(peer_params['underlay'][offset])-1)

    # VLANs
    host_vlans_list = peer_params.get('vlans')
    if host_vlans_list:
        vars['vlans'] = {}
        for vlan_id, vlan in sw_vars['vlans'].items():
            if vlan_id in host_vlans_list or vlan['name'] in host_vlans_list:
                vars['vlans'][vlan_id] = sw_vars['vlans'][vlan_id]
    else:
        vars['vlans'] = sw_vars['vlans']

    for vlan_id, vlan in vars['vlans'].items():
        if 'host_base' in vlan.keys():
            vars['vlans'][vlan_id]['host_ip'] = str(IPv4Address(vlan['host_base']) + peer_id)
    
    return vars


def frr_config_perms(file: tarfile.TarInfo) -> tarfile.TarInfo:
    """
    A tarfile filter to fix the ownership of the files going into the archive,
    e.g. remove traces of eosadmin.
    """

    file.uid = file.gid = 0
    file.uname = file.gname = "root"
    return file


@app.route("/frr.tar.gz")
def frr_config():
    """
    Render all configuration files under frr/, bundle them into a .tar.gz
    and return to client. All archived files will have the path frr/<filename>
    """

    vars = get_vars()
    template_names = os.listdir(os.path.join(basepath, 'frr'))
    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(basepath, 'frr')))
    jinja_env.undefined = jinja2.StrictUndefined

    with tempfile.TemporaryDirectory() as temp:
        for template_name in template_names:
            template = jinja_env.get_template(template_name)
            with open(os.path.join(temp, template_name), 'w') as config:
                config.write(template.render(**vars))
        
        with tarfile.open(os.path.join(temp, 'frr.tar.gz'), 'w:gz') as archive:
            archive.add(temp, arcname='frr', filter=frr_config_perms)

        with open(os.path.join(temp, 'frr.tar.gz'), 'rb') as archive:
            # Copy into memory, since the file/tempdir seem to get closed before the actual send
            # happens
            archive_bytes = io.BytesIO(archive.read())
            return send_file(archive_bytes, download_name='frr.tar.gz', mimetype='application/gzip')


@app.route("/nmstate")
def nmstate_config():
    """
    Render an nmstate configuration file containing both underlay and overlay
    network interface configurations for the given host.
    """

    vars = get_vars()

    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(basepath))
    jinja_env.undefined = jinja2.StrictUndefined
    template = jinja_env.get_template('nmstate.j2')

    return template.render(**vars)


provision_script = """
#!/bin/bash

set -euo pipefail

# Set hostname
hostnamectl set-hostname _HOSTNAME_

# Set rp_filter
grep -q rp_filter /etc/sysctl.d/99-sysctl.conf || \
    echo "net.ipv4.conf.all.rp_filter=2" >> /etc/sysctl.d/99-sysctl.conf
sysctl -p

# Disable firewall
systemctl disable --now firewalld

# Pull network config

nmstatectl apply <(curl -Ss "http://${1}:50005/nmstate")

# Pull FRR config

temp="$(mktemp -d)"
curl "http://${1}:50005/frr.tar.gz" -o "${temp}/frr.tar.gz"
rm -rf /etc/frr
cd /etc
tar xvfz "${temp}/frr.tar.gz"
rm -rf "${temp}"
chown frr: /etc/frr -R

systemctl restart frr

# Run puppet
dnf install -y puppet-agent
/opt/puppetlabs/bin/puppet agent -t --certname "$(hostname).p4.esav.fi"
"""


@app.route("/provision")
def serve_provisioning_script():
    """
    Return a script that handles the second stage of setting up the networking
    """

    vars = get_vars()
    # Use a simple replace() to avoid having to escape braces
    # in the bash script which would otherwise be interpreted by format() 
    return provision_script\
        .replace('_HOSTNAME_', vars['hostname'])\
        .strip()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50005)
