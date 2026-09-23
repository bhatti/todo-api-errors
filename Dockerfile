# SPDX-License-Identifier: Apache-2.0
# Multi-stage build for todo-api-errors service.

FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /todo-api-errors main.go

FROM alpine:3.21

RUN apk add --no-cache ca-certificates curl

COPY --from=builder /todo-api-errors /usr/local/bin/todo-api-errors
COPY openapi/ /app/openapi/

EXPOSE 8080 50051 9090

HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
  CMD curl -so /dev/null -w '%{http_code}' http://localhost:8080/v1/todos | grep -qE '(200|404)' || exit 1

ENTRYPOINT ["todo-api-errors"]
