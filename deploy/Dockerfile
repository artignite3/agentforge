FROM caddy:2-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
# The official binary carries a low-port file capability. Remove it because this
# edge uses high ports and an empty capability bounding set; otherwise exec fails.
RUN setcap -r /usr/bin/caddy && mkdir -p /data /config && chown -R 10001:10001 /data /config
COPY Caddyfile /etc/caddy/Caddyfile
USER 10001:10001
EXPOSE 8081 8443
