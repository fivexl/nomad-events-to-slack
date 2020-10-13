FROM python:3.8.6-alpine

ENV PIP_NO_CACHE_DIR=on \
    # https://github.com/pypa/pip/blob/master/src/pip/_internal/cli/cmdoptions.py
	PIP_DISABLE_PIP_VERSION_CHECK=on \
	PIP_DEFAULT_TIMEOUT=100 \
	# https://github.com/pypa/pipenv
	PKG_PIPENV_VERSION=2020.8.13

# Create user and group for running app
RUN addgroup -g 1000 app && adduser -D -u 1000 -G app app

# Copy only requirements, to cache them in docker layer
WORKDIR /pysetup
COPY ./Pipfile.lock ./Pipfile /pysetup/

# Update system and install app dependencies
RUN set -ex \
    && apk update \
    && apk upgrade \
    && pip install "pipenv==$PKG_PIPENV_VERSION" \
    && pipenv install --system --dev --deploy \
    && rm -rf /var/lib/apt/lists/* /var/cache/apk/* /usr/share/man /tmp/*

USER app
COPY --chown=app:app ./app.py /app/
WORKDIR /app

CMD ["python", "./app.py"]

