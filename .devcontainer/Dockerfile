FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

ENV PYTHONUNBUFFERED 1

# [Optional] If your requirements rarely change, uncomment this section to add them to the image.
COPY requirements.txt /tmp/pip-tmp/
RUN pip --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# [Optional] Uncomment this section to install additional OS packages.
#RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#    && apt-get -y install --no-install-recommends pgsql

RUN wget https://github.com/Wilfred/difftastic/releases/download/0.65.0/difft-x86_64-unknown-linux-gnu.tar.gz \
    && tar -xzf difft-x86_64-unknown-linux-gnu.tar.gz -C /usr/local/bin/ \
    && rm difft-x86_64-unknown-linux-gnu.tar.gz

RUN pip install --no-cache-dir \
    ruff
