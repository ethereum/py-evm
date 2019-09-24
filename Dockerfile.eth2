FROM python:3.7

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Install deps
RUN apt-get update
RUN apt-get -y install libsnappy-dev gcc g++ cmake

ARG GITREF=interop

RUN git clone https://github.com/ethereum/trinity.git .
RUN git checkout $GITREF
RUN pip install -e .[dev] --no-cache-dir
RUN pip install -U trinity --no-cache-dir

EXPOSE 30303 30303/udp
# Trinity shutdowns aren't yet solid enough to avoid the fix-unclean-shutdown
ENTRYPOINT trinity $EXTRA_OPTS fix-unclean-shutdown && trinity-beacon $EXTRA_OPTS
