FROM localstack/localstack:2.2.0

VOLUME /persisted-data

COPY setup.cfg setup.py /localstack-compere/
COPY src /localstack-compere/src

RUN . .venv/bin/activate && pip3 install jsonpickle /localstack-compere