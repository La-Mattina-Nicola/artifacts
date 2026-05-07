FROM python:3.13-alpine

ENV TZ="Europe/Brussels"

WORKDIR /artifacts

COPY requirements.txt /artifacts/
RUN pip install -r requirements.txt

COPY . /artifacts/

ENTRYPOINT ["python3","-u", "fly.py"]