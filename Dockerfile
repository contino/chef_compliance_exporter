FROM alpine:latest
MAINTAINER Emre Erkunt <emre.erkunt@contino.io>

ADD ./chef_compliance.exporter.py /opt/exporters/
ADD ./requirements.txt /opt/exporters/
WORKDIR /opt/exporters/
RUN apk update \
	&& apk upgrade \
	&& apk add python \
			   python-dev \
			   py-pip \
			   build-base \
 	&& pip install -r /opt/exporters/requirements.txt

EXPOSE 9243
CMD ["python", "/opt/exporters/chef_compliance.exporter.py"]
