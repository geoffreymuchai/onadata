import os, sys

from fabric.api import env, run, cd
from fabric.decorators import hosts


DEFAULTS = {
    'home': '/home/wsgi/srv/',
    'repo_name': 'formhub',
    }

DEPLOYMENTS = {
    'dev': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@23.21.82.214', # TODO: switch to dev.formhub.org
        'project': 'formhub-ec2',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
    },
    'prod': {
        'home': '/home/ubuntu/src/',
        'host_string': 'ubuntu@ona.io',
        'project': 'ona',
        'key_filename': os.path.expanduser('~/.ssh/ona.pem'),
        'virtualenv': '/home/ubuntu/.virtualenvs/ona'
    },
}


def run_in_virtualenv(command):
    d = {
        'activate': os.path.join(
            env.virtualenv, 'bin', 'activate'),
        'command': command,
        }
    run('source %(activate)s && %(command)s' % d)


def check_key_filename(deployment_name):
    if 'key_filename' in DEPLOYMENTS[deployment_name] and \
       not os.path.exists(DEPLOYMENTS[deployment_name]['key_filename']):
        print "Cannot find required permissions file: %s" % \
            DEPLOYMENTS[deployment_name]['key_filename']
        return False
    return True


def setup_env(deployment_name):
    env.update(DEFAULTS)
    env.update(DEPLOYMENTS[deployment_name])
    if not check_key_filename(deployment_name):
        sys.exit(1)
    env.code_src = os.path.join(env.home, env.project)
    env.pip_requirements_file = os.path.join(env.code_src, 'requirements.pip')


def deploy(deployment_name, branch='master'):
    setup_env(deployment_name)
    with cd(env.code_src):
        run("git fetch origin")
        run("git checkout origin/%s" % branch)
        run("git submodule init")
        run("git submodule update")
        run('find . -name "*.pyc" -exec rm -rf {} \;')
    # numpy pip install from requirements file fails
    run_in_virtualenv("pip install numpy")
    run_in_virtualenv("pip install -r %s" % env.pip_requirements_file)
    with cd(env.code_src):
        run_in_virtualenv("python manage.py syncdb --settings=formhub.local_settings")
        run_in_virtualenv("python manage.py migrate --settings=formhub.local_settings")
        run_in_virtualenv("python manage.py collectstatic --settings=formhub.local_settings --noinput")
    run("sudo /etc/init.d/celeryd-ona restart")
    #run("sudo /etc/init.d/celerybeat-ona restart")
    run("sudo /usr/local/bin/uwsgi --reload /var/run/ona.pid")
