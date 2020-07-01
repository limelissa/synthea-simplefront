FROM java:8-jdk-alpine

COPY entrypoint.sh /
COPY synthea.properties /

ENV SYNTHEA_SEED=
ENV SYNTHEA_SIZE=10
ENV FHIR_URL=

RUN apk update \
    && apk add git curl make unzip libstdc++ \
    && git clone https://github.com/synthetichealth/synthea.git \
    && mv synthea.properties /synthea/src/main/resources/synthea.properties \
    && cd synthea \
    && ./gradlew build -x test \
    && cd / \
    && chmod +x /entrypoint.sh

RUN apk add --no-cache --virtual .build-deps g++ python3-dev libffi-dev openssl-dev \
&& apk add --no-cache --update python3 \
&& python3 -m ensurepip \
&& pip3 install --upgrade pip setuptools \
&& rm -r /usr/lib/python*/ensurepip && \
if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
rm -r /root/.cache 

COPY src /app
WORKDIR /app

RUN apk add python3-dev
RUN pip3 install --upgrade pip
RUN pip3 install wheel 
RUN pip3 install -r requirements.txt
RUN pip3 install --upgrade setuptools

CMD python app.py