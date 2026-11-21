# Образ узлов OpenSearch для стенда ЛР-2: базовый образ + плагин
# prometheus-exporter, вшитый ДО первого старта (иначе потребовался бы
# рестарт всех узлов). Версия плагина обязана точно совпадать с версией OS.
FROM opensearchproject/opensearch:3.8.0

USER root
RUN dnf install -y jq-1.8.1-60.amzn2023 && dnf clean all
USER opensearch

ARG PLUGIN_VERSION=3.8.0.0
ARG PLUGIN_SHA256=c9e74cacd000299627be8a3b132600fa21e6b4e7912f0e6e3409528d3d44cd6a

RUN curl -fL "https://github.com/opensearch-project/opensearch-prometheus-exporter/releases/download/${PLUGIN_VERSION}/prometheus-exporter-${PLUGIN_VERSION}.zip" \
      -o /tmp/prometheus-exporter.zip \
 && echo "${PLUGIN_SHA256}  /tmp/prometheus-exporter.zip" | sha256sum -c - \
 && bin/opensearch-plugin install --batch "file:///tmp/prometheus-exporter.zip" \
 && rm -f /tmp/prometheus-exporter.zip \
 && bin/opensearch-plugin list | grep prometheus-exporter
