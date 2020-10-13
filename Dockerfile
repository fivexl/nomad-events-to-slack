FROM python:3.8.6-alpine

ENV PIP_NO_CACHE_DIR=on \
    # https://github.com/pypa/pip/blob/master/src/pip/_internal/cli/cmdoptions.py
	PIP_DISABLE_PIP_VERSION_CHECK=on \
	PIP_DEFAULT_TIMEOUT=100 \
	# https://github.com/pypa/pipenv
	PKG_PIPENV_VERSION=2020.8.13

# Copy only requirements, to cache them in docker layer
WORKDIR /pysetup
COPY ./Pipfile.lock ./Pipfile /pysetup/

# Update system and install app dependencies
RUN set -ex \
    && apk update \
    && apk upgrade \
    && pip install "pipenv==$PKG_PIPENV_VERSION" \
    && pipenv install --system --dev --deploy \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apk/* \
    && rm -rf /usr/share/man \
    && rm -rf /tmp/*

COPY ./app.py /app/
WORKDIR /app

CMD ["python", "./app.py"]

