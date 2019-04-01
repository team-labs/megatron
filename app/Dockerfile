FROM python:3.6.1
ARG version=NOT_SET

RUN adduser --no-create-home --gecos '' --disabled-password megatron-celery

RUN pip install pipenv

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN echo $version > .version

COPY Pipfile /usr/src/app/
COPY Pipfile.lock /usr/src/app/
RUN pipenv install --system --deploy --sequential

COPY . /usr/src/app
