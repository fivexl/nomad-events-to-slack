FROM python:3.8.2-slim-buster

ARG UID=1000
ARG GID=1000

ENV PIP_NO_CACHE_DIR=on \
    # https://github.com/pypa/pip/blob/master/src/pip/_internal/cli/cmdoptions.py
	PIP_DISABLE_PIP_VERSION_CHECK=on \
	PIP_DEFAULT_TIMEOUT=100 \
	# https://github.com/pypa/pipenv
	PKG_PIPENV_VERSION=2020.8.13 \

# Create user and group for running app
RUN groupadd -r -g $GID app && useradd --no-log-init -r -u $UID -g app app

# Copy only requirements, to cache them in docker layer
WORKDIR /pysetup
COPY ./app/Pipfile.lock ./app/Pipfile /pysetup/

# Building system and app dependencies
RUN set -ex \
	&& savedAptMark="$(apt-mark showmanual)" \
	&& apt-get update \
	&& apt-get install --assume-yes --no-install-recommends --no-install-suggests \
		wget \
	&& pip install "pipenv==$PKG_PIPENV_VERSION" \
	&& pipenv install --system --deploy \
	&& apt-mark auto '.*' > /dev/null \
	&& apt-mark manual $savedAptMark \
	&& find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec ldd '{}' ';' \
		| awk '/=>/ { print $(NF-1) }' \
		| sort -u \
		| xargs -r dpkg-query --search \
		| cut -d: -f1 \
		| sort -u \
		| xargs -r apt-mark manual \
	&& apt-get purge --assume-yes --auto-remove \
		--option APT::AutoRemove::RecommendsImportant=false \
		--option APT::AutoRemove::SuggestsImportant=false \
	&& rm -rf /var/lib/apt/lists/*

USER app
COPY --chown=app:app ./app /app
WORKDIR /app

CMD ["python", "./main.py"]

