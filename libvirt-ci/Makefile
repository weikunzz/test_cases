.PHONY: docs

clean-install: clean install

all: docs check

requirements:
	- yum install -y python-pip
	# Required by libvirt-diff
	- yum install -y graphviz
	# Required by ansible
	- yum install -y libffi-devel openssl-devel
	# Required by psycopg2, package from RHEL eng repo doesn't work on RHEL6
	- yum -x \*el6eng\* install -y postgresql-devel

install:
	- pip install --force-reinstall --upgrade .

check: install
	python ./bin/ci self-test

docs:
	python ./bin/ci build-docs

clean:
	- pip uninstall .
