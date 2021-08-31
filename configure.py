#!/usr/bin/env python3

from subprocess import run, PIPE, check_output, CalledProcessError
import tempfile


def get_config():
    lines = check_output("echo 'show running-config' | FastCli -p15", shell=True).decode().split('\n')
    return '\n'.join(lines[8:])


def diff(a, b):
    with tempfile.NamedTemporaryFile() as filea:
        with tempfile.NamedTemporaryFile() as fileb:
            filea.write(a.encode())
            filea.flush()
            fileb.write(b.encode())
            fileb.flush()

            return run(['diff', '-u', filea.name, fileb.name], check=False, stdout=PIPE).stdout.decode()


def apply_config(config):
    with tempfile.NamedTemporaryFile() as config_file:
        config_file.write(config.encode())
        try:
            return run(f"echo 'configure replace file:{config_file.name}' | FastCli -p15",
                       shell=True, check=True, stdout=PIPE, stderr=PIPE).stdout
        except CalledProcessError as e:
            print(e.stdout.decode())
            print(e.stderr.decode())


current_config = get_config()
candidate_config = check_output(['./render.py']).decode()
changes = diff(current_config, candidate_config)

if changes.strip() == "":
    print("No changes")
else:
    print(changes)
    print("<enter to apply>")
    input()
    apply_config(candidate_config)
