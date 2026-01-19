# Keycloak Dockerfile with custom theme

FROM maven:3.9.6-eclipse-temurin-17 AS spi-build
WORKDIR /build
COPY spi-user-storage-provider /build/spi-user-storage-provider
RUN mvn -f spi-user-storage-provider/pom.xml clean package

FROM quay.io/keycloak/keycloak:26.5.0 AS builder

# Enable health and metrics support
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true

# Configure a database vendor
# ENV KC_DB=postgres # commented out for dev mode, h2 should be used

WORKDIR /opt/keycloak
# for demonstration purposes only, please make sure to use proper certificates in production instead
RUN keytool -genkeypair -storepass password -storetype PKCS12 -keyalg RSA -keysize 2048 -dname "CN=server" -alias server -ext "SAN:c=DNS:localhost,IP:127.0.0.1" -keystore conf/server.keystore

# Copy custom theme into the build image

COPY theme/di4d /opt/keycloak/themes/di4d
# Include realm export so Keycloak can import it at startup when --import-realm is used
COPY realm-export.json /opt/keycloak/data/import/
COPY --from=spi-build /build/spi-user-storage-provider/target/spi-user-storage-provider-1.0.0.jar /opt/keycloak/providers/

RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.5.0
COPY --from=builder /opt/keycloak/ /opt/keycloak/

# change these values to point to a running postgres instance
# ENV KC_DB=postgres
# ENV KC_DB_URL=<DBURL>
# ENV KC_DB_USERNAME=<DBUSERNAME>
# ENV KC_DB_PASSWORD=<DBPASSWORD>
ENV KC_HOSTNAME=localhost

# Custom theme is now available in /opt/keycloak/themes/di4d
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start-dev"]

# For production, use:
# ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start"]
