FROM gradle:9.8.0-jdk25 AS build
WORKDIR /home/gradle/src
COPY app/ ./
RUN --mount=type=cache,target=/home/gradle/.gradle,uid=1000,gid=1000 \
    gradle --no-daemon installDist -x test

FROM eclipse-temurin:25-jre-noble
RUN useradd --system --create-home --uid 1001 appuser
COPY --from=build /home/gradle/src/build/install/rate-limit-api /opt/rate-limit-api
USER appuser
WORKDIR /opt/rate-limit-api
EXPOSE 8080 8085
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=5 \
    CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/8085 && exec 3<&-' || exit 1
ENTRYPOINT ["/opt/rate-limit-api/bin/rate-limit-api"]
