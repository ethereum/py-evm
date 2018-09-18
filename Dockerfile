FROM python:3.6
# Set up code directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install -e .[dev]  --no-cache-dir
RUN pip install -U trinity --no-cache-dir

RUN echo "Type \`trinity\` to boot or \`trinity --help\` for an overview of commands"

EXPOSE 30303 30303/udp
ENTRYPOINT ["trinity"]
