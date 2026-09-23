IMAGE   ?= plexobject/todo-api-errors
NO_CACHE ?=

.DEFAULT_GOAL := all

.PHONY: docker-build docker-push

docker-build:    ## Build multi-arch image (linux/amd64,linux/arm64) and push
	docker buildx rm multiarch 2>/dev/null || true
	docker buildx create --name multiarch --use --bootstrap \
	    --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=52428800
	docker buildx build --platform linux/amd64,linux/arm64 \
	    $(if $(NO_CACHE),--no-cache,) \
	    -t $(IMAGE):latest \
	    --push --provenance=false .

docker-push:     ## Re-push already-built image (no rebuild)
	docker push $(IMAGE):latest

.PHONY: gencert
gencert: 
	cfssl gencert \
		-initca fixtures/ca-csr.json | cfssljson -bare ca
	# ... (rest of the gencert commands remain the same)

.PHONY: test
test: 
	CGO_ENABLED=1 go test -race -parallel=4 -p=2 ./internal/...

.PHONY: vendor
vendor:
	go mod tidy

.PHONY: build
build: compile
	go build -o server main.go
	go build -o client client.go

.PHONY: compile model-compile openapi setup-deps

# Define the paths
PROTO_PATH := api/proto
GO_OUT_PATH := .
OPENAPI_OUT_PATH := openapi

.PHONY: buf-setup
buf-setup:
	@echo "Setting up buf..."
	@go install github.com/bufbuild/buf/cmd/buf@latest
	@go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	@go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
	@go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-grpc-gateway@latest
	@go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-openapiv2@latest
	@go install github.com/pseudomuto/protoc-gen-doc/cmd/protoc-gen-doc@latest
	@go install github.com/envoyproxy/protoc-gen-validate@latest

.PHONY: buf-generate
buf-generate: buf-setup
	@echo "Generating code with buf..."
	@rm -f `find api -name "*pb*.go"`
	buf dep update
	buf generate 2>/dev/null

compile: buf-generate

model-compile: buf-generate

openapi: buf-generate

# Clean up generated files
clean:
	@echo "Cleaning up generated files..."
	@rm -rf $(GO_OUT_PATH)/*.pb.go
	@rm -rf $(GO_OUT_PATH)/*.pb.gw.go
	@rm -rf $(OPENAPI_OUT_PATH)/*.json
	@rm -f `find api -name "*pb*.go"`
	#@buf clean

.PHONY: all
all: buf-generate test build 
