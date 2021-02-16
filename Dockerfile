FROM python:3.7.6-buster
MAINTAINER python_student

RUN mkdir /python_project/
RUN mkdir /python_project/dimensigon
RUN mkdir /python_project/tests
COPY ./requirements.txt /python_project
COPY ./dimensigon /python_project/dimensigon
COPY ./requirements-test.txt /python_project
COPY ./setup.py ./python_project
COPY ./README.md ./python_project
COPY ./Makefile ./python_project

WORKDIR /python_project

RUN pip install --upgrade pip

RUN cd /python_project; pip install -e .
RUN pip3 install -r requirements-test.txt

CMD "make test"
ENV PYTHONDONTWRITEBYTECODE=true
