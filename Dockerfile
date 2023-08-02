ARG LOCALSTACK_VERSION=latest
FROM localstack/localstack:${LOCALSTACK_VERSION}

LABEL maintainer="Graham Esau (hello@graham.cool)"

VOLUME /persisted-data

COPY setup.cfg setup.py /localstack-compere/
COPY src /localstack-compere/src

RUN . .venv/bin/activate && pip3 install jsonpickle /localstack-compere