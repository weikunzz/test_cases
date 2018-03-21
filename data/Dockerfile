# Should use provision base for internal compability
FROM provisioner-base

# We need rhscl on RHEL for python36
COPY ./docker/etc/yum.repos.d/rhscl.repo /etc/yum.repos.d/rhscl.repo

RUN yum install -y rh-python36 rh-python36-python-devel rh-python36-python-setuptools rh-python36-python-pip rh-nodejs6 nss_wrapper postgresql-devel && yum clean all

WORKDIR /app/

VOLUME ["/app/node_modules/"]

COPY . /app/

# Don't use scl enable to enable python 3 because bkr requires python2
RUN source /opt/rh/rh-nodejs6/enable &&\
        source /opt/rh/rh-python36/enable &&\
        pip install --upgrade pip setuptools &&\
        ./setup.sh --venv /app/.venv

ENTRYPOINT ["/app/docker/entrypoint.sh", "--venv", "/app/.venv"]
